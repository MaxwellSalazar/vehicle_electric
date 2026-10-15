"""Analisis estadistico extendido de la telemetria del prototipo.

Calcula potencia electrica registrada, energia registrada por distancia,
relaciones velocidad-potencia, caida de tension, pruebas entre sesiones,
ICC, geometria de rutas y figuras asociadas. Los resultados se guardan en
``resultados_extendidos.json``.
"""

import json
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests

import process_real_data_and_generate_figures as base

ROOT = Path(__file__).resolve().parent
SEED = 20260702
N_BOOT = 4000
BLOCK = 30
MAX_GAP_S = 30
NOMINAL_MOTOR_POWER_W = 2000.0
JULY_DATES = {f"2026-07-{d}" for d in ("25", "27", "28", "29", "30", "31")}


def prepare() -> pd.DataFrame:
    _, data = base.load_curated_data()
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["session"] = data["timestamp"].dt.strftime("%Y-%m-%d")
    counts = data["session"].value_counts()
    data = data[data["session"].isin(counts[counts >= base.MIN_SESSION_RECORDS].index)].copy()
    data = data.rename(
        columns={
            "Velocidad_estimada_km_h": "v",
            "Corriente_Motor": "i_motor",
            "Voltaje_Bateria": "v_bat",
            "Distancia_desde_registro_anterior_m": "dist_m",
        }
    )
    data["power_w"] = data["v_bat"] * data["i_motor"]
    data["dt_s"] = data.groupby("session")["timestamp"].diff().dt.total_seconds()
    data["month"] = np.where(data["session"].isin(JULY_DATES), "julio", "agosto")
    return data.reset_index(drop=True)


def block_bootstrap(values: np.ndarray, stat, rng: np.random.Generator) -> tuple[float, float]:
    n = len(values)
    n_blocks = int(np.ceil(n / BLOCK))
    starts_max = max(n - BLOCK, 0)
    out = np.empty(N_BOOT)
    for k in range(N_BOOT):
        starts = rng.integers(0, starts_max + 1, n_blocks)
        sample = np.concatenate([values[s : s + BLOCK] for s in starts])[:n]
        out[k] = stat(sample)
    return tuple(np.percentile(out, [2.5, 97.5]))


def block_bootstrap_ratio(num: np.ndarray, den: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    n = len(num)
    n_blocks = int(np.ceil(n / BLOCK))
    starts_max = max(n - BLOCK, 0)
    out = np.empty(N_BOOT)
    for k in range(N_BOOT):
        starts = rng.integers(0, starts_max + 1, n_blocks)
        idx = np.concatenate([np.arange(s, s + BLOCK) for s in starts])[:n]
        out[k] = num[idx].sum() / den[idx].sum()
    return tuple(np.percentile(out, [2.5, 97.5]))


def lag1(x: np.ndarray) -> float:
    x = x - x.mean()
    return float((x[:-1] * x[1:]).sum() / (x * x).sum())


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    u = stats.mannwhitneyu(a, b, alternative="two-sided").statistic
    return float(2 * u / (len(a) * len(b)) - 1)


def dunn_test(data: pd.DataFrame, value: str) -> pd.DataFrame:
    ranks = data[value].rank()
    n = len(data)
    groups = {k: ranks[g.index] for k, g in data.groupby("session")}
    tie = data[value].value_counts()
    tie_corr = (tie**3 - tie).sum() / (12 * (n - 1))
    rows = []
    for a, b in combinations(groups, 2):
        se = np.sqrt((n * (n + 1) / 12 - tie_corr) * (1 / len(groups[a]) + 1 / len(groups[b])))
        z = (groups[a].mean() - groups[b].mean()) / se
        rows.append((a, b, 2 * stats.norm.sf(abs(z))))
    out = pd.DataFrame(rows, columns=["a", "b", "p"])
    out["p_holm"] = multipletests(out["p"], method="holm")[1]
    return out


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def main() -> None:
    rng = np.random.default_rng(SEED)
    data = prepare()
    res: dict = {"n": int(len(data)), "sessions": sorted(data["session"].unique().tolist())}

    # 1. Potencia electrica registrada ------------------------------------
    p = data["power_w"]
    res["power_pooled"] = {
        "mean": p.mean(), "sd": p.std(), "median": p.median(),
        "p5": p.quantile(.05), "p95": p.quantile(.95), "p99": p.quantile(.99),
        "min": p.min(), "max": p.max(),
        "abs_p95": p.abs().quantile(.95), "abs_p99": p.abs().quantile(.99),
        "abs_max": p.abs().max(),
        "abs_max_pct_nominal": p.abs().max() / NOMINAL_MOTOR_POWER_W * 100,
        "share_negative_pct": (data["i_motor"] < 0).mean() * 100,
        "saturation_limit_a": data["i_motor"].abs().max(),
        "saturation_share_pct": (data["i_motor"].abs() >= data["i_motor"].abs().max() - 1e-9).mean() * 100,
    }
    per = []
    for s, g in data.groupby("session"):
        pw = g["power_w"].to_numpy()
        per.append({
            "session": s, "n": len(g),
            "i_mean": g["i_motor"].mean(), "p_mean": pw.mean(), "p_sd": pw.std(ddof=1),
            "p_median": float(np.median(pw)), "p_p95": float(np.percentile(pw, 95)),
            "abs_p_mean": np.abs(pw).mean(), "abs_p_p95": float(np.percentile(np.abs(pw), 95)),
            "neg_pct": (g["i_motor"] < 0).mean() * 100,
            "p_mean_ci": block_bootstrap(pw, np.mean, rng),
            "abs_p_mean_ci": block_bootstrap(np.abs(pw), np.mean, rng),
            "v_mean": g["v"].mean(), "v_mean_ci": block_bootstrap(g["v"].to_numpy(), np.mean, rng),
            "v_median": g["v"].median(), "v_median_ci": block_bootstrap(g["v"].to_numpy(), np.median, rng),
            "lag1_v": lag1(g["v"].to_numpy()), "lag1_p": lag1(pw),
        })
        per[-1]["n_eff_v"] = len(g) * (1 - per[-1]["lag1_v"]) / (1 + per[-1]["lag1_v"])
    res["per_session"] = per

    # 2. Energia registrada y consumo especifico --------------------------
    energy = []
    for s, g in data.groupby("session"):
        g = g[(g["dt_s"].notna()) & (g["dt_s"] <= MAX_GAP_S)]
        dt = g["dt_s"].to_numpy()
        pw = g["power_w"].to_numpy()
        dist_km = g["dist_m"].to_numpy() / 1000
        net_wh = pw * dt / 3600
        gross_wh = np.abs(pw) * dt / 3600
        row = {
            "session": s, "n_int": len(g), "time_h": dt.sum() / 3600,
            "dist_km": dist_km.sum(),
            "net_wh": net_wh.sum(), "gross_wh": gross_wh.sum(),
            "net_wh_km": net_wh.sum() / dist_km.sum(),
            "gross_wh_km": gross_wh.sum() / dist_km.sum(),
            "net_wh_km_ci": block_bootstrap_ratio(net_wh, dist_km, rng),
            "gross_wh_km_ci": block_bootstrap_ratio(gross_wh, dist_km, rng),
        }
        energy.append(row)
    res["energy"] = energy
    gw = np.array([e["gross_wh_km"] for e in energy])
    nw = np.array([e["net_wh_km"] for e in energy])
    res["energy_summary"] = {
        "gross_wh_km_mean": gw.mean(), "gross_wh_km_sd": gw.std(ddof=1),
        "gross_wh_km_median": float(np.median(gw)), "gross_wh_km_min": gw.min(), "gross_wh_km_max": gw.max(),
        "net_wh_km_mean": nw.mean(), "net_wh_km_sd": nw.std(ddof=1),
        "net_positive_sessions": int((nw > 0).sum()), "net_negative_sessions": int((nw < 0).sum()),
        "gross_wh_km_t_ci": tuple(stats.t.interval(.95, len(gw) - 1, gw.mean(), gw.std(ddof=1) / np.sqrt(len(gw)))),
    }

    # 3. Velocidad - corriente / potencia ---------------------------------
    rel = []
    for s, g in data.groupby("session"):
        r1 = stats.spearmanr(g["v"], g["i_motor"])
        r2 = stats.spearmanr(g["v"], g["power_w"])
        r3 = stats.spearmanr(g["v"], g["i_motor"].abs())
        rel.append({"session": s, "rho_i": r1.statistic, "p_i": r1.pvalue,
                    "rho_p": r2.statistic, "p_p": r2.pvalue,
                    "rho_abs_i": r3.statistic, "p_abs_i": r3.pvalue})
    res["speed_relation_per_session"] = rel
    rhos = np.array([r["rho_abs_i"] for r in rel])
    res["rho_abs_i_range"] = (rhos.min(), rhos.max())

    data["abs_i"] = data["i_motor"].abs()
    data["abs_p"] = data["power_w"].abs()
    data["v_c"] = data["v"] - data["v"].mean()
    ols = smf.ols("abs_p ~ v_c", data).fit(cov_type="cluster", cov_kwds={"groups": data["session"]})
    quad = smf.ols("abs_p ~ v_c + I(v_c**2)", data).fit(cov_type="cluster", cov_kwds={"groups": data["session"]})
    rlm = smf.rlm("abs_p ~ v_c", data, M=sm.robust.norms.HuberT()).fit()
    mixed = smf.mixedlm("abs_p ~ v_c", data, groups=data["session"]).fit(reml=True)
    null = smf.mixedlm("abs_p ~ 1", data, groups=data["session"]).fit(reml=True)
    icc_p = float(null.cov_re.iloc[0, 0] / (null.cov_re.iloc[0, 0] + null.scale))
    null_v = smf.mixedlm("v ~ 1", data, groups=data["session"]).fit(reml=True)
    icc_v = float(null_v.cov_re.iloc[0, 0] / (null_v.cov_re.iloc[0, 0] + null_v.scale))
    res["models_abs_power_vs_speed"] = {
        "ols_slope": ols.params["v_c"], "ols_slope_ci": tuple(ols.conf_int().loc["v_c"]),
        "ols_r2": ols.rsquared,
        "quad_r2": quad.rsquared, "quad_b2": quad.params["I(v_c ** 2)"], "quad_b2_p": quad.pvalues["I(v_c ** 2)"],
        "quad_aic": quad.aic, "ols_aic": ols.aic,
        "huber_slope": rlm.params["v_c"], "huber_slope_ci": tuple(rlm.conf_int().loc["v_c"]),
        "mixed_slope": mixed.params["v_c"], "mixed_slope_ci": tuple(mixed.conf_int().loc["v_c"]),
        "mixed_slope_p": mixed.pvalues["v_c"],
        "mixed_sd_session": float(np.sqrt(mixed.cov_re.iloc[0, 0])), "mixed_sd_resid": float(np.sqrt(mixed.scale)),
        "icc_abs_power": icc_p, "icc_speed": icc_v,
    }

    # 4. Caida de tension vs corriente ------------------------------------
    sag = []
    for s, g in data.groupby("session"):
        m = smf.ols("v_bat ~ i_motor", g).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        sag.append({"session": s, "n": len(g), "r_ohm": -m.params["i_motor"],
                    "r_ci": tuple(-m.conf_int().loc["i_motor"][::-1]),
                    "v0": m.params["Intercept"], "r2": m.rsquared, "p": m.pvalues["i_motor"],
                    "rho": stats.spearmanr(g["v_bat"], g["i_motor"]).statistic})
    res["sag_per_session"] = sag
    fe = smf.ols("v_bat ~ i_motor + C(session)", data).fit(cov_type="cluster", cov_kwds={"groups": data["session"]})
    res["sag_pooled_fe"] = {"r_ohm": -fe.params["i_motor"], "ci": tuple(-fe.conf_int().loc["i_motor"][::-1]),
                            "p": fe.pvalues["i_motor"], "r2": fe.rsquared}
    r_vals = np.array([x["r_ohm"] for x in sag])
    res["sag_sign_consistency"] = {"positive_r_sessions": int((r_vals > 0).sum()), "negative_r_sessions": int((r_vals < 0).sum())}
    # Pooled by within-session ranges of I (sign-agnostic): |I| vs voltage
    fe_abs = smf.ols("v_bat ~ abs_i + C(session)", data).fit(cov_type="cluster", cov_kwds={"groups": data["session"]})
    res["sag_pooled_abs_fe"] = {"slope": fe_abs.params["abs_i"], "ci": tuple(fe_abs.conf_int().loc["abs_i"]), "p": fe_abs.pvalues["abs_i"]}

    # 5-6. Pruebas entre sesiones y meses ---------------------------------
    tests = {}
    for var, label in (("v", "speed"), ("abs_p", "abs_power"), ("v_bat", "v_bat")):
        groups = [g[var].to_numpy() for _, g in data.groupby("session")]
        h = stats.kruskal(*groups)
        eps2 = (h.statistic - len(groups) + 1) / (len(data) - len(groups))
        jul = data.loc[data["month"] == "julio", var].to_numpy()
        ago = data.loc[data["month"] == "agosto", var].to_numpy()
        mw = stats.mannwhitneyu(jul, ago, alternative="two-sided")
        dunn = dunn_test(data.reset_index(drop=True), var)
        tests[label] = {
            "kw_h": h.statistic, "kw_p": h.pvalue, "eps2": eps2,
            "mw_u": mw.statistic, "mw_p": mw.pvalue, "cliffs_delta": cliffs_delta(jul, ago),
            "jul_median": float(np.median(jul)), "ago_median": float(np.median(ago)),
            "dunn_pairs": len(dunn), "dunn_sig_holm": int((dunn["p_holm"] < .05).sum()),
        }
    res["tests"] = tests

    # 7. Geometria de ruta -------------------------------------------------
    routes = []
    for s, g in data.groupby("session"):
        lat, lon = g["Latitud"].to_numpy(), g["Longitud"].to_numpy()
        d0 = haversine_m(lat[0], lon[0], lat, lon)
        lat_c, lon_c = lat.mean(), lon.mean()
        rg = np.sqrt(np.mean(haversine_m(lat_c, lon_c, lat, lon) ** 2))
        ext_ns = haversine_m(lat.min(), lon.mean(), lat.max(), lon.mean())
        ext_ew = haversine_m(lat.mean(), lon.min(), lat.mean(), lon.max())
        path = g["dist_m"].sum()
        routes.append({"session": s, "path_km": path / 1000, "max_disp_km": d0.max() / 1000,
                       "rg_km": rg / 1000, "ext_ns_km": ext_ns / 1000, "ext_ew_km": ext_ew / 1000,
                       "path_over_2maxdisp": path / (2 * d0.max())})
    res["routes"] = routes

    # Cuadro de reconciliación con el consumo
    Path(ROOT / "resultados_extendidos.json").write_text(
        json.dumps(res, indent=2, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o)),
        encoding="utf-8",
    )
    make_figures(data, energy, sag)
    print(json.dumps(res, indent=1, default=lambda o: float(o)))


def make_figures(data: pd.DataFrame, energy: list, sag: list) -> None:
    short = lambda s: s[8:10] + "/" + s[5:7]
    sessions = sorted(data["session"].unique())
    colors = plt.cm.tab10(np.linspace(0, 1, len(sessions)))

    # Figure A: recorded power and specific energy indicator
    fig, ax = plt.subplots(1, 3, figsize=(10.5, 3.3))
    ax[0].scatter(data["v"], data["power_w"], s=4, alpha=.2, color="#2878b5")
    ax[0].axhline(0, color="k", lw=.6)
    ax[0].set_xlabel("Estimated speed (km/h)")
    ax[0].set_ylabel("Recorded power $V_{bat}I_{motor}$ (W)")
    ax[0].set_title("(a) Power vs. speed")
    box = [data.loc[data["session"] == s, "power_w"] for s in sessions]
    bp = ax[1].boxplot(box, tick_labels=[short(s) for s in sessions], showfliers=False, patch_artist=True)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c); patch.set_alpha(.7)
    ax[1].axhline(0, color="k", lw=.6)
    ax[1].set_xlabel("Session (dd/mm)"); ax[1].set_ylabel("Recorded power (W)")
    ax[1].set_title("(b) Power by session"); ax[1].tick_params(axis="x", rotation=45)
    x = np.arange(len(energy))
    y = np.array([e["gross_wh_km"] for e in energy])
    lo = y - np.array([e["gross_wh_km_ci"][0] for e in energy])
    hi = np.array([e["gross_wh_km_ci"][1] for e in energy]) - y
    ax[2].errorbar(x, y, yerr=[lo, hi], fmt="o", color="#2878b5", capsize=3)
    ax[2].set_xticks(x, [short(e["session"]) for e in energy], rotation=45)
    ax[2].set_xlabel("Session (dd/mm)"); ax[2].set_ylabel("Recorded gross energy (Wh/km)")
    ax[2].set_title("(c) Energy per km (95% bootstrap CI)")
    save(fig, "fig_5_potencia_energia")

    # Figure B: voltage drop
    fig, ax = plt.subplots(1, 2, figsize=(8.5, 3.3))
    for s, c in zip(sessions, colors):
        g = data[data["session"] == s]
        ax[0].scatter(g["i_motor"], g["v_bat"], s=3, alpha=.25, color=c, label=short(s))
    ax[0].set_xlabel("Recorded motor current (A)"); ax[0].set_ylabel("Battery voltage (V)")
    ax[0].set_title("(a) Voltage vs. current"); ax[0].legend(markerscale=4, ncol=2, fontsize=6)
    r = np.array([s["r_ohm"] for s in sag])
    lo = r - np.array([s["r_ci"][0] for s in sag]); hi = np.array([s["r_ci"][1] for s in sag]) - r
    ax[1].errorbar(np.arange(len(r)), r, yerr=[lo, hi], fmt="o", color="#d49428", capsize=3)
    ax[1].axhline(0, color="k", lw=.6)
    ax[1].set_xticks(np.arange(len(r)), [short(s["session"]) for s in sag], rotation=45)
    ax[1].set_xlabel("Session (dd/mm)"); ax[1].set_ylabel(r"Slope $-\Delta V/\Delta I$ ($\Omega$)")
    ax[1].set_title("(b) Effective resistance by session (95% CI)")
    save(fig, "fig_6_caida_tension")


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(ROOT / "figuras" / f"{name}.png", bbox_inches="tight")
    fig.savefig(ROOT / "figuras" / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

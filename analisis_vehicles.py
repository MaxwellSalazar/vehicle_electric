"""Analisis complementario para la version destinada a *Vehicles*.

Valida la velocidad con GPS, perfila la conduccion (velocidad-aceleracion),
estudia saturacion y desplazamiento de cero de la corriente del motor,
examina el canal de panel frente a Voc/Vmp del arreglo, hace analisis de
sensibilidad y tabula los motivos de exclusion. Guarda resultados_vehicles.json
y las figuras 7 a 9.
"""

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import analisis_estadistico_extendido as ext
import process_real_data_and_generate_figures as base

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figuras"
SEED = 20260702
SAT_A = 6.549
VOC_ARRAY, VMP_ARRAY, ISC_MODULE = 39.6, 34.2, 6.16
R_EARTH = 6371008.8


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def load_full() -> pd.DataFrame:
    _, raw = base.load_curated_data()
    raw = raw.sort_values("timestamp").reset_index(drop=True)
    raw["session"] = raw["timestamp"].dt.strftime("%Y-%m-%d")
    raw = raw.rename(
        columns={
            "Velocidad_estimada_km_h": "v",
            "Corriente_Motor": "i_motor",
            "Corriente_Panel": "i_panel",
            "Voltaje_Panel": "v_panel",
            "Voltaje_Bateria": "v_bat",
            "Distancia_desde_registro_anterior_m": "dist_m",
            "Latitud": "lat",
            "Longitud": "lon",
        }
    )
    g = raw.groupby("session")
    raw["dt_s"] = g["timestamp"].diff().dt.total_seconds()
    raw["lat0"], raw["lon0"] = g["lat"].shift(), g["lon"].shift()
    raw["hav_m"] = haversine_m(raw["lat0"], raw["lon0"], raw["lat"], raw["lon"])
    raw["v_hav"] = raw["hav_m"] / raw["dt_s"] * 3.6
    raw["v_dist"] = raw["dist_m"] / raw["dt_s"] * 3.6
    raw["acc"] = g["v"].diff() / 3.6 / raw["dt_s"]
    raw["power_w"] = raw["v_bat"] * raw["i_motor"]
    raw["hour"] = raw["timestamp"].dt.hour + raw["timestamp"].dt.minute / 60
    return raw


def regular(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["dt_s"] >= 4) & (df["dt_s"] <= 6)]


def bland_altman(a: np.ndarray, b: np.ndarray) -> dict:
    d = a - b
    bias, sd = d.mean(), d.std(ddof=1)
    rho_prop = stats.spearmanr((a + b) / 2, d)[0]
    return {
        "n": int(len(d)),
        "bias": float(bias),
        "sd": float(sd),
        "loa_low": float(bias - 1.96 * sd),
        "loa_high": float(bias + 1.96 * sd),
        "rmse": float(np.sqrt((d**2).mean())),
        "mae": float(np.abs(d).mean()),
        "median_abs": float(np.median(np.abs(d))),
        "p95_abs": float(np.percentile(np.abs(d), 95)),
        "corr_pearson": float(np.corrcoef(a, b)[0, 1]),
        "prop_bias_spearman": float(rho_prop),
    }


def gps_validation(data: pd.DataFrame) -> dict:
    reg = regular(data).dropna(subset=["v_hav"])
    out = {
        "supplied_vs_gps": bland_altman(reg["v"].to_numpy(), reg["v_hav"].to_numpy()),
        "supplied_vs_dist": bland_altman(reg["v"].to_numpy(), reg["v_dist"].to_numpy()),
        "dist_vs_haversine_m": bland_altman(reg["dist_m"].to_numpy(), reg["hav_m"].to_numpy()),
    }
    out["by_session"] = {
        s: bland_altman(x["v"].to_numpy(), x["v_hav"].to_numpy())
        for s, x in reg.groupby("session")
        if len(x) > 30
    }
    # Aceleracion maxima fisicamente plausible para un vehiculo ligero
    out["acc_abs_gt_3"] = float((regular(data)["acc"].abs() > 3).mean())
    return out, reg


def driving_profile(data: pd.DataFrame) -> dict:
    reg = regular(data).dropna(subset=["acc"])
    a = reg["acc"]
    out = {
        "n": int(len(reg)),
        "acc_mean": float(a.mean()),
        "acc_sd": float(a.std()),
        "acc_p5": float(a.quantile(0.05)),
        "acc_p95": float(a.quantile(0.95)),
        "acc_max": float(a.max()),
        "dec_min": float(a.min()),
        "share_acc": float((a > 0.1).mean()),
        "share_dec": float((a < -0.1).mean()),
        "share_cruise": float((a.abs() <= 0.1).mean()),
        "pos_kinetic_acc": float((reg["v"] / 3.6 * a.clip(lower=0)).mean()),
        "rpa": float(
            (reg["v"] / 3.6 * a.clip(lower=0)).sum() * 5 / (reg["v"] / 3.6 * 5).sum()
        ),
    }
    bins = [0, 5, 10, 15, 20, 30, 120]
    out["speed_bins_share"] = (
        pd.cut(data["v"], bins, right=False).value_counts(normalize=True).sort_index().round(4).astype(float).rename(str).to_dict()
    )
    # Pausas: huecos > 30 s entre registros consecutivos dentro de una sesion
    gaps = data["dt_s"].dropna()
    out["gaps_gt_30s"] = int((gaps > 30).sum())
    out["gaps_gt_60s"] = int((gaps > 60).sum())
    out["gap_share_time_gt30"] = float(gaps[(gaps > 30) & (gaps < 3600)].sum() / gaps[gaps < 3600].sum())
    out["gap_by_session"] = {
        s: int(((x["dt_s"] > 30) & (x["dt_s"] < 3600)).sum()) for s, x in data.groupby("session")
    }
    # micro-viajes: segmentos separados por huecos > 30 s
    seg = (data["dt_s"].isna() | (data["dt_s"] > 30)).cumsum()
    mt = data.groupby(seg).agg(n=("v", "size"), dur=("timestamp", lambda t: (t.max() - t.min()).total_seconds()), vmean=("v", "mean"), dist=("dist_m", "sum"))
    mt = mt[mt["n"] >= 6]
    out["microtrips"] = {
        "count": int(len(mt)),
        "dur_median_s": float(mt["dur"].median()),
        "dur_iqr_s": [float(mt["dur"].quantile(0.25)), float(mt["dur"].quantile(0.75))],
        "dist_median_m": float(mt["dist"].median()),
        "vmean_median": float(mt["vmean"].median()),
    }
    # Acc vs corriente por sesion
    rows = {}
    for s, x in reg.groupby("session"):
        rows[s] = {
            "rho_acc_i": float(stats.spearmanr(x["acc"], x["i_motor"])[0]),
            "rho_acc_absi": float(stats.spearmanr(x["acc"], x["i_motor"].abs())[0]),
            "n": int(len(x)),
        }
    out["acc_vs_current_by_session"] = rows
    r_all = stats.spearmanr(reg["acc"], reg["i_motor"])
    out["acc_vs_current_all"] = {"rho": float(r_all[0]), "n": int(len(reg))}
    # Estructura: corriente media por categoria de aceleracion
    cat = pd.cut(reg["acc"], [-10, -0.3, -0.1, 0.1, 0.3, 10], labels=["dec_fuerte", "dec", "crucero", "acel", "acel_fuerte"])
    out["i_by_acc_cat"] = reg.groupby(cat, observed=True)["i_motor"].agg(["mean", "std", "size"]).round(3).to_dict("index")
    out["i_by_acc_cat"] = {str(k): v for k, v in out["i_by_acc_cat"].items()}
    return out, reg


def saturation_and_offset(data: pd.DataFrame) -> dict:
    sat = data["i_motor"].abs() >= SAT_A
    out = {
        "sat_share": float(sat.mean()),
        "sat_pos_share": float((data["i_motor"] >= SAT_A).mean()),
        "sat_neg_share": float((data["i_motor"] <= -SAT_A).mean()),
        "i_max": float(data["i_motor"].max()),
        "i_min": float(data["i_motor"].min()),
        "by_session": {s: float(x) for s, x in sat.groupby(data["session"]).mean().items()},
    }
    # tramos consecutivos saturados
    runs = []
    for _, x in data.groupby("session"):
        s = (x["i_motor"].abs() >= SAT_A).to_numpy()
        ok = ((x["dt_s"] <= 10) | x["dt_s"].isna()).to_numpy()
        cur = 0
        for flag, cont in zip(s, ok):
            if flag and (cur == 0 or cont):
                cur += 1
            else:
                if cur:
                    runs.append(cur)
                cur = 1 if flag else 0
        if cur:
            runs.append(cur)
    runs = np.array(runs)
    out["runs"] = {
        "count": int(len(runs)),
        "mean_s": float(runs.mean() * 5),
        "median_s": float(np.median(runs) * 5),
        "max_s": float(runs.max() * 5),
        "share_in_runs_ge3": float(runs[runs >= 3].sum() / runs.sum()),
    }
    # Valores distintos: la senal parece cuantizada
    out["unique_values_abs"] = int(data["i_motor"].abs().round(4).nunique())
    top = data["i_motor"].abs().round(3).value_counts().head(5)
    out["top_abs_values"] = {str(k): int(v) for k, v in top.items()}
    # Offset: corriente a baja velocidad (v<3 km/h) y a velocidad alta
    low = data[data["v"] < 3]
    out["offset_low_speed"] = {
        "n": int(len(low)),
        "mean": float(low["i_motor"].mean()) if len(low) else None,
        "median": float(low["i_motor"].median()) if len(low) else None,
    }
    mid = data[(data["v"] >= 1) & (data["v"] < 5)]
    out["offset_v_lt5"] = {"n": int(len(mid)), "mean": float(mid["i_motor"].mean()), "median": float(mid["i_motor"].median())}
    out["mean_by_session"] = {s: float(x) for s, x in data.groupby("session")["i_motor"].mean().items()}
    # Intercepto de i_motor vs v por sesion (extrapolado a v=0) por MCO
    inter = {}
    for s, x in data.groupby("session"):
        sl, ic, r, p, se = stats.linregress(x["v"], x["i_motor"])
        inter[s] = {"slope": float(sl), "intercept": float(ic), "r2": float(r**2)}
    out["intercept_by_session"] = inter
    # Fraccion de observaciones con i en [-0.5, 0.5]
    out["near_zero_share"] = float((data["i_motor"].abs() < 0.5).mean())
    return out


def panel_channel(data: pd.DataFrame, full: pd.DataFrame) -> dict:
    vp, ip = data["v_panel"], data["i_panel"]
    big = full[full["i_panel"].abs() > ISC_MODULE]
    out = {
        "full_ip_min": float(full["i_panel"].min()),
        "full_ip_max": float(full["i_panel"].max()),
        "full_n_gt_isc": int(len(big)),
        "full_n_gt_isc_dates": {k: int(v) for k, v in big["session"].value_counts().items()},
        "ip_min": float(ip.min()),
        "ip_max": float(ip.max()),
        "ip_cap_share": float((ip.abs() >= 3.27).mean()),
        "ip_cap_pos_share": float((ip >= 3.27).mean()),
        "ip_cap_neg_share": float((ip <= -3.27).mean()),
        "ip_unique": int(ip.round(3).nunique()),
        "vp_min": float(vp.min()),
        "vp_max": float(vp.max()),
        "vp_median": float(vp.median()),
        "vp_gt_voc": float((vp > VOC_ARRAY).mean()),
        "vp_gt_vmp": float((vp > VMP_ARRAY).mean()),
        "vp_between_vmp_voc": float(((vp > VMP_ARRAY) & (vp <= VOC_ARRAY)).mean()),
        "vp_lt_vmp": float((vp <= VMP_ARRAY).mean()),
        "ip_abs_gt_isc": float((ip.abs() > ISC_MODULE).mean()),
        "ip_abs_gt_isc_x2": float((ip.abs() > 2 * ISC_MODULE).mean()),
        "ip_median": float(ip.median()),
        "ip_p5_p95": [float(ip.quantile(0.05)), float(ip.quantile(0.95))],
        "ip_pos_share": float((ip > 0).mean()),
        "ip_exact_zero": float((ip == 0).mean()),
        "corr_vp_vbat_spearman": float(stats.spearmanr(vp, data["v_bat"])[0]),
        "corr_ip_imotor_spearman": float(stats.spearmanr(ip, data["i_motor"])[0]),
        "corr_vp_vbat_by_session": {
            s: float(stats.spearmanr(x["v_panel"], x["v_bat"])[0]) for s, x in data.groupby("session")
        },
    }
    h = data["timestamp"].dt.hour
    byh = data.groupby(h).agg(n=("v_panel", "size"), vp=("v_panel", "median"), ip=("i_panel", "median"), vb=("v_bat", "median"))
    out["by_hour"] = {int(k): {kk: float(vv) for kk, vv in row.items()} for k, row in byh.iterrows()}
    r_v = stats.spearmanr(data["hour"], data["v_panel"])
    r_i = stats.spearmanr(data["hour"], data["i_panel"])
    out["hour_vs_vp"] = [float(r_v[0]), float(r_v[1])]
    out["hour_vs_ip"] = [float(r_i[0]), float(r_i[1])]
    # Correlacion horaria por sesion (mediana de rho) evitando mezclar fechas
    rv = [stats.spearmanr(x["hour"], x["v_panel"])[0] for _, x in data.groupby("session") if len(x) > 100]
    ri = [stats.spearmanr(x["hour"], x["i_panel"])[0] for _, x in data.groupby("session") if len(x) > 100]
    out["hour_vs_vp_by_session_median"] = float(np.median(rv))
    out["hour_vs_ip_by_session_median"] = float(np.median(ri))
    out["by_session_vp"] = {s: float(x) for s, x in data.groupby("session")["v_panel"].median().items()}
    out["by_session_ip"] = {s: float(x) for s, x in data.groupby("session")["i_panel"].median().items()}
    return out


def energy_gross(df: pd.DataFrame, max_gap: float) -> float:
    vals = []
    for _, x in df.groupby("session"):
        dt = x["dt_s"].to_numpy()
        ok = (dt > 0) & (dt <= max_gap)
        e = (x["power_w"].abs().to_numpy() * dt)[ok].sum() / 3600
        d = x["dist_m"].to_numpy()[ok].sum() / 1000
        vals.append(e / d if d > 0 else np.nan)
    return float(np.nanmean(vals))


def sensitivity(full: pd.DataFrame) -> dict:
    out = {}
    counts = full["session"].value_counts()
    for cov in (50, 100, 200, 400):
        keep = counts[counts >= cov].index
        d = full[full["session"].isin(keep)]
        sess = d.groupby("session")
        out[f"cov{cov}"] = {
            "sessions": int(len(keep)),
            "n": int(len(d)),
            "vmean": float(sess["v"].mean().mean()),
            "sat": float((d["i_motor"].abs() >= SAT_A).mean()),
            "pmax": float(d["power_w"].abs().max()),
            "gross": energy_gross(d, 30),
            "r2_v_p": float(stats.linregress(d["v"], d["power_w"].abs())[2] ** 2),
        }
    base_d = full[full["session"].isin(counts[counts >= 100].index)]
    for gap in (10, 30, 60, 120):
        out[f"gap{gap}"] = {"gross": energy_gross(base_d, gap)}
    for vmin in (1, 3, 5):
        d = base_d[base_d["v"] >= vmin]
        out[f"vmin{vmin}"] = {
            "n": int(len(d)),
            "vmean": float(d.groupby("session")["v"].mean().mean()),
            "gross": energy_gross(d, 30),
            "sat": float((d["i_motor"].abs() >= SAT_A).mean()),
        }
    d = base_d[base_d["i_motor"].abs() < SAT_A]
    out["sin_saturados"] = {
        "n": int(len(d)),
        "gross": energy_gross(d, 30),
        "r2_v_p": float(stats.linregress(d["v"], d["power_w"].abs())[2] ** 2),
        "pmax": float(d["power_w"].abs().max()),
    }
    rng = np.random.default_rng(SEED)
    for blk in (15, 30, 60):
        ext.BLOCK = blk
        ext.N_BOOT = 1000
        res = []
        for s, x in base_d.groupby("session"):
            vals = x["v"].to_numpy()
            lo, hi = ext.block_bootstrap(vals, np.mean, rng)
            res.append(hi - lo)
        out[f"block{blk}"] = {"ic_width_mean_kmh": float(np.mean(res))}
    ext.BLOCK, ext.N_BOOT = 30, 4000
    return out


def exclusion_table() -> dict:
    xl = pd.ExcelFile(ROOT / "Vehiculo_solar_graficas_mapas_OSM.xlsx")
    exc = xl.parse("Datos excluidos")
    exc = exc.rename(columns={exc.columns[-1]: "motivo"})
    exc["date"] = pd.to_datetime(exc["Hoja"], format="%d-%m-%Y").dt.strftime("%m-%d")

    def norm(m):
        parts = []
        for p in str(m).split(";"):
            p = p.strip().lower()
            if p.startswith("corriente_panel"):
                parts.append("i_panel_rango")
            elif p.startswith("voltaje_bateria") and "mad" in p:
                parts.append("v_bat_atipico")
            elif p.startswith("voltaje_bateria"):
                parts.append("v_bat_ausente")
            elif p.startswith("voltaje_panel") and "mad" in p:
                parts.append("v_panel_atipico")
            elif p.startswith("voltaje_panel"):
                parts.append("v_panel_ausente")
            else:
                parts.append(p)
        return parts
    exc["cats"] = exc["motivo"].map(norm)
    cats = sorted({c for l in exc["cats"] for c in l})
    out = {"total": int(len(exc)), "all_motives_raw": exc["motivo"].value_counts().head(10).to_dict(), "categories": {}}
    for c in cats:
        out["categories"][c] = int(sum(c in l for l in exc["cats"]))
    # cuantas filas con 1,2+ criterios
    out["n_criteria_dist"] = exc["cats"].map(lambda l: len(set(l))).value_counts().sort_index().to_dict()
    out["by_date"] = {}
    for d, x in exc.groupby("date"):
        out["by_date"][d] = {"excluded": int(len(x))}
        for c in cats:
            out["by_date"][d][c] = int(sum(c in l for l in x["cats"]))
        out["by_date"][d]["v_gt20"] = int((x["Velocidad_estimada_km_h"] > 20).sum())
        out["by_date"][d]["v_bat_zero"] = int((x["Voltaje_Bateria"] <= 0.5).sum())
    return out


def route_geometry_fig(data: pd.DataFrame) -> None:
    sessions = sorted(data["session"].unique())
    fig, axes = plt.subplots(2, 4, figsize=(12, 6.2))
    for ax, s in zip(axes.ravel(), sessions):
        x = data[data["session"] == s]
        lat0, lon0 = x["lat"].mean(), x["lon"].mean()
        e = (np.radians(x["lon"] - lon0) * np.cos(np.radians(lat0)) * R_EARTH) / 1000
        n = (np.radians(x["lat"] - lat0) * R_EARTH) / 1000
        ax.plot(e, n, color="0.6", lw=0.4)
        sc = ax.scatter(e, n, c=x["v"], s=4, cmap="viridis", vmin=0, vmax=40)
        ax.set_aspect("equal")
        ax.set_title(pd.Timestamp(s).strftime("%d/%m"), fontsize=10)
        ax.set_xlabel("East (km)", fontsize=8)
        ax.set_ylabel("North (km)", fontsize=8)
        ax.tick_params(labelsize=7)
        if "07-27" <= s[5:] <= "07-31":
            ax.set_xlim(-0.6, 0.8)
            ax.set_ylim(-1.0, 0.8)
        else:
            ax.set_xlim(-0.15, 0.15)
            ax.set_ylim(-0.15, 0.15)
    fig.colorbar(sc, ax=axes, shrink=0.8, label="Estimated speed (km/h)")
    fig.savefig(FIG / "fig_9_geometria_rutas.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / "fig_9_geometria_rutas.pdf", bbox_inches="tight")
    plt.close(fig)


def profile_fig(reg_acc: pd.DataFrame) -> None:
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.0))
    h = ax[0].hist2d(reg_acc["v"], reg_acc["acc"], bins=[np.arange(0, 52, 2), np.arange(-2.5, 2.55, 0.25)], cmap="viridis", norm=matplotlib.colors.LogNorm())
    fig.colorbar(h[3], ax=ax[0], label="Observations")
    ax[0].set_xlabel("Speed (km/h)")
    ax[0].set_ylabel("Acceleration (m/s$^2$)")
    ax[0].set_title("(a) Speed--acceleration distribution", fontsize=10)
    ax[1].scatter(reg_acc["acc"], reg_acc["i_motor"], s=3, alpha=0.2, color="tab:red")
    ax[1].set_xlim(-2, 1.2)
    ax[1].set_xlabel("Acceleration (m/s$^2$)")
    ax[1].set_ylabel("$I_{\\mathrm{motor}}$ (A)")
    ax[1].set_title("(b) Recorded motor current vs. acceleration", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "fig_7_perfil_conduccion.png", dpi=300)
    fig.savefig(FIG / "fig_7_perfil_conduccion.pdf")
    plt.close(fig)


def panel_fig(data: pd.DataFrame) -> None:
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.0))
    ax[0].hist(data["v_panel"], bins=60, color="tab:orange", alpha=0.85)
    ax[0].axvline(VMP_ARRAY, color="k", ls="--", label="$V_{mp}$ array (34.2 V)")
    ax[0].axvline(VOC_ARRAY, color="k", ls=":", label="$V_{oc}$ array (39.6 V)")
    ax[0].set_xlabel("Voltage in the channel labeled panel (V)")
    ax[0].set_ylabel("Observations")
    ax[0].legend(fontsize=8)
    ax[0].set_title("(a) Distribution", fontsize=10)
    for s, x in data.groupby("session"):
        g = x.groupby(x["timestamp"].dt.hour)["v_panel"].median()
        ax[1].plot(g.index, g.values, marker="o", ms=3, lw=0.8, label=pd.Timestamp(s).strftime("%d/%m"))
    ax[1].axhline(VOC_ARRAY, color="k", ls=":")
    ax[1].set_xlabel("Local time")
    ax[1].set_ylabel("Median $V_{\\mathrm{panel}}$ (V)")
    ax[1].legend(fontsize=7, ncol=2)
    ax[1].set_title("(b) Median by hour and session", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "fig_8_canal_panel.png", dpi=300)
    fig.savefig(FIG / "fig_8_canal_panel.pdf")
    plt.close(fig)


def few_clusters(data: pd.DataFrame) -> dict:
    import statsmodels.formula.api as smf

    d = data.copy()
    d["abs_p"] = d["power_w"].abs()
    d["vc"] = d["v"] - d["v"].mean()
    out = {}
    for name, formula, term in (
        ("rsag", "v_bat ~ i_motor + C(session)", "i_motor"),
        ("v_abs_p", "abs_p ~ vc", "vc"),
    ):
        fit = smf.ols(formula, d).fit(
            cov_type="cluster",
            cov_kwds={"groups": pd.factorize(d["session"])[0], "use_correction": True},
            use_t=True,
        )
        ci = fit.conf_int().loc[term]
        out[name] = {"coef": float(fit.params[term]), "se": float(fit.bse[term]), "ci": [float(ci[0]), float(ci[1])], "df": float(fit.df_resid), "r2": float(fit.rsquared)}
    slopes = []
    for s, x in d.groupby("session"):
        slopes.append(stats.linregress(x["i_motor"], x["v_bat"])[0] * -1)
    slopes = np.array(slopes)
    se = slopes.std(ddof=1) / np.sqrt(len(slopes))
    tcrit = stats.t.ppf(0.975, len(slopes) - 1)
    out["rsag_session_mean"] = {"mean": float(slopes.mean()), "ci": [float(slopes.mean() - tcrit * se), float(slopes.mean() + tcrit * se)], "min": float(slopes.min()), "max": float(slopes.max())}
    # R2 intrasesion de |P| ~ v
    r2 = [stats.linregress(x["v"], x["abs_p"])[2] ** 2 for _, x in d.groupby("session")]
    out["r2_v_absp_by_session"] = [float(v) for v in r2]
    return out


def unifilar_fig() -> None:
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(11, 3.9))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 3.9)
    ax.axis("off")
    boxes = [
        (0.2, "PV array\n2 × 100 Wp in series\n$V_{mp}$ = 34.2 V; $V_{oc}$ = 39.6 V", "#2878b5"),
        (3.0, "MPPT converter\nDC HOUSE, 300 W\ninput: 13–65 V", "#2c9d78"),
        (5.8, "Gel battery bank\n4 × 12 V, 60 Ah\nnominal bus: 48 V", "#d49327"),
        (8.6, "Controller + BLDC motor\n2 kW nominal\nDesign $I_{max}$: 46.3 A", "#7452a3"),
    ]
    centers = []
    for x, txt, col in boxes:
        ax.add_patch(FancyBboxPatch((x, 1.5), 2.2, 1.3, boxstyle="round,pad=0.03", fc=col, ec="k", lw=1.2))
        ax.text(x + 1.1, 2.15, txt, ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        centers.append(x)
    for x0, x1 in ((2.4, 3.0), (5.2, 5.8), (8.0, 8.6)):
        ax.annotate("", xy=(x1, 2.15), xytext=(x0, 2.15), arrowprops=dict(arrowstyle="-|>", lw=1.8, color="0.2"))
    marks = [
        (2.7, "$V_{\\mathrm{panel}}$, $I_{\\mathrm{panel}}$\n(channel labeled panel)", "?"),
        (5.5, "$V_{\\mathrm{bat}}$\n(location assumed)", "?"),
        (8.3, "$I_{\\mathrm{motor}}$\n(channel labeled motor)", "?"),
    ]
    for x, label, q in marks:
        ax.plot([x, x], [1.5, 1.0], color="0.3", lw=1, ls="--")
        ax.scatter([x], [1.0], s=260, facecolor="white", edgecolor="crimson", lw=1.8, zorder=3)
        ax.text(x, 1.0, q, ha="center", va="center", color="crimson", fontsize=10, fontweight="bold", zorder=4)
        ax.text(x, 0.45, label, ha="center", va="center", fontsize=8)
    ax.text(5.5, 3.55, "Single-line diagram with recorded channels", ha="center", fontsize=10, fontweight="bold")
    ax.text(5.5, 0.02, "? = recorded channel with undocumented connection point, polarity, and calibration", ha="center", fontsize=8, color="crimson")
    fig.savefig(FIG / "fig_2_unifilar_medidas.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / "fig_2_unifilar_medidas.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    full = load_full()
    counts = full["session"].value_counts()
    data = full[full["session"].isin(counts[counts >= base.MIN_SESSION_RECORDS].index)].copy()
    res = {}
    res["gps"], reg_gps = gps_validation(data)
    res["profile"], reg_acc = driving_profile(data)
    res["saturation"] = saturation_and_offset(data)
    res["panel"] = panel_channel(data, full)
    res["few_clusters"] = few_clusters(data)
    res["sensitivity"] = sensitivity(full)
    res["exclusion"] = exclusion_table()
    profile_fig(reg_acc)
    panel_fig(data)
    route_geometry_fig(data)
    unifilar_fig()
    (ROOT / "resultados_vehicles.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

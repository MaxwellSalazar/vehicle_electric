from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
JULY_FILE = ROOT / "datos_solar_movimiento_separado_por_fechas julio filtrado.xlsx"
AUGUST_FILE = ROOT / "datos_solar_agosto_movimiento_separado_por_fechas filtrado.xlsx"
CURATED_FILE = ROOT / "Vehiculo_solar_graficas_mapas_OSM.xlsx"
OUTPUT_DIR = ROOT / "figuras"
MIN_SESSION_RECORDS = 100
PANEL_SHORT_CIRCUIT_CURRENT_A = 6.16

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "text.usetex": False,
    }
)


def load_movement_sources() -> pd.DataFrame:
    frames = []
    for path in (JULY_FILE, AUGUST_FILE):
        if not path.is_file():
            raise FileNotFoundError(f"Missing movement source: {path}")
        workbook = pd.ExcelFile(path)
        for sheet in workbook.sheet_names:
            if sheet.strip().lower() == "resumen por fecha":
                continue
            data = pd.read_excel(path, sheet_name=sheet)
            if data.empty:
                continue
            if "Fecha" not in data:
                raise ValueError(f"Missing Fecha column in {path.name}, {sheet}")
            frames.append(data.assign(source_file=path.name, source_sheet=sheet))
    if not frames:
        raise ValueError("No movement records were found in the source workbooks.")
    return pd.concat(frames, ignore_index=True)


def load_curated_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not CURATED_FILE.is_file():
        raise FileNotFoundError(f"Missing curated workbook: {CURATED_FILE}")
    workbook = pd.ExcelFile(CURATED_FILE)
    summary = pd.read_excel(CURATED_FILE, sheet_name="Resumen depurado")
    summary = summary.dropna(subset=[summary.columns[0]]).iloc[:, :10].copy()
    summary.columns = [
        "date",
        "records",
        "distance_km",
        "mean_speed_kmh",
        "max_speed_kmh",
        "mean_motor_current_a",
        "max_abs_motor_current_a",
        "mean_battery_voltage_v",
        "mean_panel_voltage_v",
        "mean_panel_current_a",
    ]
    summary["date"] = pd.to_datetime(summary["date"], errors="raise")
    numeric_columns = summary.columns.drop("date")
    summary[numeric_columns] = summary[numeric_columns].apply(
        pd.to_numeric, errors="raise"
    )

    frames = []
    for sheet in workbook.sheet_names[3:]:
        data = pd.read_excel(CURATED_FILE, sheet_name=sheet, header=2)
        data = data.loc[:, ~data.columns.astype(str).str.startswith("Unnamed")]
        data = data.dropna(subset=["Fecha"]).copy()
        data["timestamp"] = pd.to_datetime(
            data["Fecha"], dayfirst=True, errors="raise"
        )
        for column in (
            "Voltaje_Bateria",
            "Voltaje_Panel",
            "Corriente_Motor",
            "Corriente_Panel",
            "Distancia_desde_registro_anterior_m",
            "Velocidad_estimada_km_h",
            "Latitud",
            "Longitud",
        ):
            data[column] = pd.to_numeric(data[column], errors="coerce")
        frames.append(data)
    if not frames:
        raise ValueError("No daily records were found in the curated workbook.")
    return summary, pd.concat(frames, ignore_index=True)


def validate_sources(movement: pd.DataFrame, summary: pd.DataFrame, data: pd.DataFrame) -> None:
    expected_movement_records = 4277
    expected_curated_records = 3052
    if len(movement) != expected_movement_records:
        raise ValueError(
            f"Expected {expected_movement_records} movement records; got {len(movement)}."
        )
    if int(summary["records"].sum()) != expected_curated_records:
        raise ValueError("The curated daily summary does not total 3052 records.")
    if len(data) != expected_curated_records:
        raise ValueError(
            f"Expected {expected_curated_records} curated rows; got {len(data)}."
        )

    daily = (
        data.groupby(data["timestamp"].dt.normalize())
        .agg(
            records=("timestamp", "size"),
            distance_km=("Distancia_desde_registro_anterior_m", "sum"),
        )
        .reset_index(names="date")
    )
    check = summary[["date", "records", "distance_km"]].merge(
        daily, on="date", suffixes=("_summary", "_rows"), validate="one_to_one"
    )
    if len(check) != len(summary):
        raise ValueError("Daily summary dates do not match the curated data sheets.")
    if not np.array_equal(check["records_summary"], check["records_rows"]):
        raise ValueError("Daily record counts do not match the curated data sheets.")
    if not np.allclose(
        check["distance_km_summary"], check["distance_km_rows"] / 1000, atol=1e-6
    ):
        raise ValueError("Daily distance totals do not match the curated data sheets.")


def save_figure(fig: plt.Figure, name: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def create_architecture_figure() -> None:
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.axis("off")
    boxes = (
        (
            "Arreglo fotovoltaico\n2 × 100 Wp en serie\n$V_{mp}$ total reportado: 34,2 V",
            0.12,
            "#2878b5",
        ),
        (
            "Convertidor elevador MPPT\nDC HOUSE, 300 W\nMedidas de entrada/salida no disponibles",
            0.38,
            "#2d9d78",
        ),
        (
            "Banco de baterías\n4 × 12 V, gel, 60 Ah\nBus nominal: 48 V",
            0.64,
            "#d49428",
        ),
        (
            "Controlador y motor BLDC\n48 V, 2 kW nominales\nPunto de medida de corriente no trazado",
            0.88,
            "#7551a1",
        ),
    )
    for label, x, color in boxes:
        ax.text(
            x,
            0.62,
            label,
            ha="center",
            va="center",
            color="white",
            weight="bold",
            fontsize=8,
            bbox={
                "boxstyle": "round,pad=0.75",
                "facecolor": color,
                "edgecolor": "black",
            },
        )
    for x0, x1 in ((0.23, 0.27), (0.49, 0.53), (0.75, 0.79)):
        ax.annotate(
            "",
            xy=(x1, 0.62),
            xytext=(x0, 0.62),
            arrowprops={"arrowstyle": "->", "lw": 1.8, "color": "#2c3e50"},
        )
    ax.text(
        0.5,
        0.12,
        "Configuración nominal según DATOS CARRO; esquema funcional, no balance energético medido.",
        ha="center",
        va="center",
        fontsize=8,
    )
    save_figure(fig, "fig_1_arquitectura_sistema")


def create_session_figure(summary: pd.DataFrame) -> None:
    sessions = summary.loc[summary["records"] >= MIN_SESSION_RECORDS].sort_values(
        "date"
    )
    if len(sessions) != 8:
        raise ValueError(f"Expected 8 sessions with >=100 records; got {len(sessions)}.")
    labels = [
        f"{day:%d/%m}\n(n={int(count)})"
        for day, count in zip(sessions["date"], sessions["records"])
    ]
    x = np.arange(len(sessions))
    fig, ax_distance = plt.subplots(figsize=(9, 4.4))
    bars = ax_distance.bar(
        x, sessions["distance_km"], color="#4c91c7", label="Distancia registrada"
    )
    ax_distance.set_ylabel("Suma de incrementos registrados (km)")
    ax_distance.set_xticks(x, labels)
    ax_distance.set_xlabel("Fecha (2026)")
    ax_distance.grid(True, axis="y", alpha=0.3)
    ax_speed = ax_distance.twinx()
    ax_speed.plot(
        x,
        sessions["mean_speed_kmh"],
        color="#d65f35",
        marker="o",
        linewidth=1.7,
        label="Velocidad media estimada",
    )
    ax_speed.set_ylabel("Velocidad media estimada (km/h)")
    ax_distance.set_title("Sesiones con al menos 100 observaciones")
    for bar, count in zip(bars, sessions["records"]):
        ax_distance.annotate(
            f"{bar.get_height():.1f}",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    handles_1, labels_1 = ax_distance.get_legend_handles_labels()
    handles_2, labels_2 = ax_speed.get_legend_handles_labels()
    ax_distance.legend(handles_1 + handles_2, labels_1 + labels_2, loc="upper left")
    save_figure(fig, "fig_2_resumen_sesiones")


def create_speed_distribution_figure(data: pd.DataFrame) -> None:
    sessions = [
        (date, day["Velocidad_estimada_km_h"].dropna().to_numpy())
        for date, day in data.groupby(data["timestamp"].dt.normalize(), sort=True)
        if len(day) >= MIN_SESSION_RECORDS
    ]
    if len(sessions) != 8 or any(values.size == 0 for _, values in sessions):
        raise ValueError("Expected eight sessions with speed observations.")

    labels = [f"{date:%d/%m}\n(n={values.size})" for date, values in sessions]
    values_by_session = [values for _, values in sessions]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.boxplot(
        values_by_session,
        tick_labels=labels,
        showfliers=False,
        widths=0.55,
        medianprops={"color": "#b33a2b", "linewidth": 1.6},
        boxprops={"color": "#2878b5"},
        whiskerprops={"color": "#2878b5"},
        capprops={"color": "#2878b5"},
    )
    rng = np.random.default_rng(173)
    for position, values in enumerate(values_by_session, start=1):
        jitter = rng.uniform(-0.17, 0.17, size=values.size)
        ax.scatter(
            position + jitter,
            values,
            s=7,
            alpha=0.2,
            color="#2878b5",
            rasterized=True,
        )
    ax.set_xlabel("Fecha (2026)")
    ax.set_ylabel("Velocidad estimada por observación (km/h)")
    ax.set_title("Distribución de velocidades registradas en cada sesión")
    ax.grid(True, axis="y", alpha=0.3)
    save_figure(fig, "fig_3_distribucion_velocidad")


def create_panel_current_figure(data: pd.DataFrame) -> None:
    grouped = list(data.groupby(data["timestamp"].dt.normalize(), sort=True))
    rng = np.random.default_rng(173)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    colors = plt.get_cmap("tab10")
    for index, (date, day) in enumerate(grouped):
        x = index + rng.uniform(-0.16, 0.16, size=len(day))
        ax.scatter(
            x,
            day["Corriente_Panel"],
            s=7,
            alpha=0.38,
            color=colors(index % 10),
            label=f"{date:%d/%m}",
            rasterized=True,
        )
    ax.axhline(
        PANEL_SHORT_CIRCUIT_CURRENT_A,
        color="#a33",
        linestyle="--",
        linewidth=1,
        label=r"$\pm I_{\mathrm{sc}}$ documentada",
    )
    ax.axhline(-PANEL_SHORT_CIRCUIT_CURRENT_A, color="#a33", linestyle="--", linewidth=1)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_yscale("symlog", linthresh=PANEL_SHORT_CIRCUIT_CURRENT_A)
    ax.set_xticks(range(len(grouped)), [date.strftime("%d/%m") for date, _ in grouped])
    ax.set_xlabel("Fecha (2026)")
    ax.set_ylabel("Corriente registrada en el canal «panel» (A)")
    ax.set_title("Canal de corriente del panel y valor de referencia documental")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.18), frameon=False)
    save_figure(fig, "fig_4_calidad_corriente_panel")


def describe_sessions(summary: pd.DataFrame, data: pd.DataFrame) -> None:
    sessions = summary.loc[summary["records"] >= MIN_SESSION_RECORDS].copy()
    if len(sessions) != 8:
        raise ValueError(f"Expected 8 sessions with >=100 records; got {len(sessions)}.")

    print("\nBetween-session descriptive statistics (n = dates):")
    for column in ("records", "distance_km", "mean_speed_kmh"):
        values = sessions[column]
        print(
            f"{column}: mean={values.mean():.3f}, SD={values.std(ddof=1):.3f}, "
            f"median={values.median():.3f}, "
            f"IQR={values.quantile(.75) - values.quantile(.25):.3f}, "
            f"range={values.min():.3f}--{values.max():.3f}"
        )

    speed_summaries = (
        data.loc[data["timestamp"].dt.normalize().isin(sessions["date"])]
        .groupby(data["timestamp"].dt.normalize())
        .agg(
            median_speed=("Velocidad_estimada_km_h", "median"),
            speed_q1=("Velocidad_estimada_km_h", lambda values: values.quantile(.25)),
            speed_q3=("Velocidad_estimada_km_h", lambda values: values.quantile(.75)),
        )
    )
    speed_summaries["speed_iqr"] = (
        speed_summaries["speed_q3"] - speed_summaries["speed_q1"]
    )
    for column in ("median_speed", "speed_iqr"):
        values = speed_summaries[column]
        print(
            f"{column}: mean={values.mean():.3f}, SD={values.std(ddof=1):.3f}, "
            f"median={values.median():.3f}, "
            f"IQR={values.quantile(.75) - values.quantile(.25):.3f}, "
            f"range={values.min():.3f}--{values.max():.3f}"
        )

    rho = sessions["distance_km"].rank().corr(
        sessions["mean_speed_kmh"].rank()
    )
    print(f"Exploratory Spearman rho (distance vs. mean speed): {rho:.3f}, n=8")


def main() -> None:
    movement = load_movement_sources()
    summary, curated = load_curated_data()
    validate_sources(movement, summary, curated)

    retained = int(summary["records"].sum())
    excluded = len(movement) - retained
    sessions = summary.loc[summary["records"] >= MIN_SESSION_RECORDS]
    print(f"Movement-filtered input records: {len(movement)}")
    print(f"Retained curated records: {retained} ({retained / len(movement):.2%})")
    print(f"Excluded records: {excluded} ({excluded / len(movement):.2%})")
    print(f"Dates with curated records: {len(summary)}")
    print(f"Sessions with at least {MIN_SESSION_RECORDS} records: {len(sessions)}")
    print(f"Retained distance increments in those sessions: {sessions['distance_km'].sum():.5f} km")
    print(
        "Panel-current range: "
        f"{curated['Corriente_Panel'].min():.2f} to "
        f"{curated['Corriente_Panel'].max():.2f} A"
    )
    describe_sessions(summary, curated)

    create_architecture_figure()
    create_session_figure(summary)
    create_speed_distribution_figure(curated)
    create_panel_current_figure(curated)


if __name__ == "__main__":
    main()

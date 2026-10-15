# Field telemetry and route characterization of a solar-assisted light electric vehicle

This repository contains the manuscript prepared for *Vehicles*, its supplementary
tables, the source workbooks used in the analysis, and Python scripts that validate
the workbooks, calculate the reported statistics, and generate figures.

The study is a field-data and measurement-quality assessment of a solar-assisted
light electric vehicle prototype in Sangolquí, Ecuador. It describes how the
prototype was used and evaluates whether the available GPS and electrical
telemetry can support claims about vehicle energy consumption or photovoltaic
generation. The analysis concludes that the electrical measurement chain is not
documented or reliable enough for those claims.

## Study at a glance

The prototype is a single-seat vehicle with a steel chassis and chain drive. Its
documented main components are:

| Component | Documented specification |
| --- | --- |
| Traction motor | 48 V, 2 kW nominal BLDC motor |
| Photovoltaic array | Two flexible 100 Wp modules connected in series; 200 Wp total |
| MPPT converter | DC HOUSE boost converter, 300 W, 13–65 V input range |
| Battery bank | Four 12 V, 60 Ah gel batteries connected in series; 48 V nominal |
| Study location | Sangolquí, Ecuador, approximately 2500 m above sea level |

These are specifications, not measurements from the field campaign. The campaign
did not record irradiance, module temperature, battery state of charge, or
independently measured energy at the battery terminals. Consequently, this work
does **not** evaluate photovoltaic performance, MPPT performance, solar
contribution to traction, range, or actual energy consumption.

## Data and analysis

### Input data

The analysis uses three Excel workbooks:

1. `datos_solar_movimiento_separado_por_fechas julio filtrado.xlsx` — July
   movement records.
2. `datos_solar_agosto_movimiento_separado_por_fechas filtrado.xlsx` — August
   movement records.
3. `Vehiculo_solar_graficas_mapas_OSM.xlsx` — consolidated, curated data,
   daily summaries, and records excluded during curation.

The two monthly workbooks contain 4,277 movement records in total: 3,714 from
July and 563 from August. As described in the manuscript, these inputs had
already been filtered to estimated speeds between 1 and 120 km/h. The consolidated
workbook contains 3,052 retained records across 11 dates and 1,225 excluded
records. The code expects the consolidated workbook to be present; it does not
re-create this workbook or independently apply the curation rules to the monthly
workbooks.

The consolidated workbook is also an important part of the reproducibility
record. Its `Resumen depurado` sheet supplies the daily summary, its
`Datos excluidos` sheet supplies exclusion reasons, and subsequent daily sheets
contain the retained observations. The scripts check that the workbook totals
and daily counts agree with the monthly movement workbooks.

The manuscript reports exclusions related to zero or out-of-range battery and
panel voltage, voltage outliers identified using a six-median-absolute-deviation
(6 MAD) threshold, and panel-current values whose absolute value exceeds 100 A.
A record can meet more than one exclusion criterion. Current signs are preserved
in the analysis.

### What was analyzed

The retained records include timestamps (typically about five seconds apart),
estimated speed, GPS latitude and longitude, distance increments, battery
voltage, and voltage and current in channels labeled as “panel” and “motor.”
The analysis covers:

- **Data coverage and quality:** numbers of retained and excluded observations,
  reasons for exclusion, and the distribution of records across dates.
- **Routes and speed:** distance increments, mean and maximum speed, session
  geometry, and the contrast between a repeatedly traveled route and confined
  circuits. Route plots use relative local coordinates rather than publishing
  georeferenced tracks.
- **Speed consistency and driving profile:** comparison of reported speed with
  speed calculated from consecutive GPS coordinates using the Haversine
  distance; acceleration, speed–acceleration patterns, and micro-trips.
- **Electrical telemetry quality:** current limits, zero readings, session-level
  current offsets, relationships with speed and acceleration, and the panel
  channel in relation to documented photovoltaic-array voltages.
- **Sensitivity and uncertainty:** session-level moving-block bootstrap
  confidence intervals and sensitivity to coverage thresholds, integration-gap
  limits, minimum speed, saturated readings, and bootstrap block length.

For speed consistency and acceleration, consecutive records are used only when
their time difference is 4–6 seconds. Coordinate-derived speed uses the
Haversine distance. Acceleration is the change in reported speed divided by
that time interval. Micro-trips are segments of at least six records separated
by gaps longer than 30 seconds. The gross recorded-energy indicator integrates
the absolute value of recorded battery-voltage × motor-current over intervals
of up to 30 seconds and divides by the corresponding recorded distance.

Confidence intervals are calculated per session using a moving-block bootstrap
(30 observations per block, 4,000 resamples, seed `20260702`). Sensitivity
checks use minimum session sizes of 50, 100, 200, and 400 observations;
integration-gap caps of 10, 30, 60, and 120 seconds; minimum speeds of 1, 3,
and 5 km/h; exclusion of saturated current observations; and block lengths of
15, 30, and 60 observations. These settings describe the calculations in the
analysis scripts; they do not correct the limitations of the underlying
measurements.

For between-session summaries, a session is defined as one date with at least
100 retained observations. Eight dates meet this threshold, accounting for
3,029 records. The other three dates remain in the coverage tables but are not
included in between-session summaries. The threshold is an analytical grouping
rule, not evidence that a session is representative.

The eight analyzed dates are 25 and 27–31 July, and 11–12 August 2026. The
analysis treats each date as a session.

### Main findings

- **Coverage:** 3,052 of 4,277 movement records were retained (71.4%). Of the
  1,225 exclusions, 572 (46.7%) were associated with zero or invalid battery
  voltage; exclusion categories can overlap.
- **Routes:** the repeated route from 27–31 July had a north–south extent of
  approximately 1.4 km and session mean speeds of 14.7–16.0 km/h. The
  confined circuits had maximum displacements below 0.15 km and mean speeds of
  7.7–8.7 km/h.
- **GPS speed consistency:** reported speed matched the speed recalculated
  from GPS coordinates (RMSE approximately 0.003 km/h). This is not an
  independent validation.
- **Electrical signals:** motor current was bounded at ±6.55 A, with 6.9% of
  analyzed observations at the limit. Panel current was bounded at ±3.28 A,
  with 34.4% zero readings. Sensor calibration, polarity, and connection
  points are undocumented.
- **Energy indicators:** the gross recorded-signal indicator averaged
  12.96 Wh/km with a 30 s integration-gap limit. Changing that limit to
  10–120 s changed the estimate to 11.59–18.84 Wh/km. These values are not
  valid measurements of vehicle energy consumption.

### Interpretation and limitations

The reported speed agrees almost exactly with speed recalculated from the GPS
coordinates. Because both quantities are derived from the same GPS positions,
this is a consistency check, not an independent validation.

The recorded motor-current channel is bounded at approximately ±6.55 A and has
session-dependent offsets. It does not show the expected relationship with
speed or acceleration. The channel labeled as panel current is also bounded,
with about 34% zero readings in the analyzed sessions. Sensor connection
locations, calibration, and polarity are undocumented.

The manuscript calculates voltage-times-current and integrated values for
diagnostic purposes, but treats them only as **recorded-signal indicators**.
They are not validated estimates of energy consumption or photovoltaic
generation. In particular, do not interpret the reported Wh/km figures as
vehicle consumption.

The conclusions are limited to one vehicle and eight adequately covered
sessions in July and August 2026. The data do not support generalization to
other vehicles, routes, or seasons.

## Repository contents

| File or directory | Purpose |
| --- | --- |
| `articulo_vehicles.tex` | Main English-language manuscript for *Vehicles*. |
| `articulo_vehicles.pdf` | Compiled manuscript. |
| `material_suplementario_vehicles.tex` | Supplementary tables, including session statistics and sensitivity analysis. |
| `material_suplementario_vehicles.pdf` | Compiled supplementary material. |
| `analisis_vehicles.py` | GPS consistency, driving-profile, current-quality, panel-channel, sensitivity, exclusion, and route-figure analysis. Writes `resultados_vehicles.json` and figures 2 and 7–9 used by the manuscript. |
| `analisis_estadistico_extendido.py` | Electrical-signal indicators, session comparisons, uncertainty analysis, and figures 5–6. Writes `resultados_extendidos.json`. |
| `process_real_data_and_generate_figures.py` | Loads and validates all three workbooks, checks their record and distance totals, prints descriptive summaries, and generates additional overview figures. |
| `DATOS CARRO.md` | Documented technical specifications for the prototype. |
| `datos_solar_movimiento_separado_por_fechas julio filtrado.xlsx` | July movement input workbook. |
| `datos_solar_agosto_movimiento_separado_por_fechas filtrado.xlsx` | August movement input workbook. |
| `Vehiculo_solar_graficas_mapas_OSM.xlsx` | Curated data, exclusions, and daily summaries required by the analysis scripts. |
| `figuras/` | Figure files. The manuscript uses the PDF assets `fig_2_unifilar_medidas`, `fig_9_geometria_rutas`, `fig_7_perfil_conduccion`, `fig_5_potencia_energia`, and `fig_8_canal_panel`. `fig_6_caida_tension` is generated by the analysis but is not included in the final manuscript. |
| `auto.jpg` | Illustrative vehicle schematic used in the manuscript. |
| `Definitions/` | MDPI class, bibliography styles, and supporting files required to compile the manuscript. |

Running the analysis scripts overwrites their corresponding JSON results and
figure files. The scripts do not overwrite the Excel workbooks or manuscript
source.

## Reproducing the analysis

Run commands from the project root so the scripts can find the workbooks by
their expected filenames. Python 3 and the following packages are required:
NumPy, pandas, Matplotlib, SciPy, statsmodels, and openpyxl.

### 1. Create a Python environment

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install numpy pandas matplotlib scipy statsmodels openpyxl
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy pandas matplotlib scipy statsmodels openpyxl
```

### 2. Check the workbooks and generate the overview figures

```bash
python process_real_data_and_generate_figures.py
```

This step validates the number of movement records, the retained-data total,
and the daily record and distance summaries. It also creates supplementary
overview figures in `figuras/`. Some of these overview figures are not the
English-language figures included in the manuscript.

### 3. Recalculate the manuscript analyses and figures

```bash
python analisis_estadistico_extendido.py
python analisis_vehicles.py
```

The scripts use the fixed random seed `20260702`. The statistical script uses
4,000 moving-block bootstrap resamples and a default block length of 30
observations. Outputs include:

- `resultados_extendidos.json` — extended statistical results.
- `resultados_vehicles.json` — GPS, driving-profile, sensor-quality,
  sensitivity, and exclusion results.
- Refreshed PDF and PNG figures in `figuras/`.

The first analysis script creates the `fig_5_potencia_energia` and
`fig_6_caida_tension` outputs; only the former is included in the manuscript.
The second creates the `fig_2_unifilar_medidas`, `fig_7_perfil_conduccion`,
`fig_8_canal_panel`, and `fig_9_geometria_rutas` outputs used by the
manuscript. Figure 1 is the descriptive `auto.jpg` illustration. Run the
overview script first if you also want the workbook
consistency checks; the analysis scripts themselves load the consolidated
workbook directly.

To reconstruct the curation itself from the monthly movement workbooks, the
underlying selection and exclusion decisions must also be available. The
analysis scripts consume the pre-curated consolidated workbook; they do not
infer those decisions or rebuild it.

## Reproducing the PDFs

Install a LaTeX distribution that includes `latexmk` and `pdflatex` (for
example, TeX Live). From the project root, compile the manuscript and
supplementary material:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error articulo_vehicles.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error material_suplementario_vehicles.tex
```

The outputs are `articulo_vehicles.pdf` and
`material_suplementario_vehicles.pdf`. The MDPI class and support files are in
`Definitions/`.

## Data availability

The manuscript identifies the source repository for the data as
<https://github.com/MaxwellSalazar/vehicle_electric>. For a reproducible run,
make sure the three Excel workbooks listed above are available in the project
root and retain their expected filenames.

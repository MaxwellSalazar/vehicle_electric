import pandas as pd
import numpy as np

df = pd.read_excel('datos_solar_PLOMO.xlsx', sheet_name=0)
print("Shape:", df.shape)
print("Columns:", df.columns.tolist())

# Convert datetime
df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)
t_start = df['Fecha'].min()
t_end = df['Fecha'].max()
elapsed_sec = (t_end - t_start).total_seconds()
print(f"Start: {t_start}, End: {t_end}")
print(f"Elapsed time: {elapsed_sec} s = {elapsed_sec/60:.2f} min = {elapsed_sec/3600:.4f} h")

# Time deltas
df['dt'] = df['Fecha'].diff().dt.total_seconds().fillna(5.0)
print("\nTime deltas summary (seconds):")
print(df['dt'].describe())
print("\nTime deltas value counts:")
print(df['dt'].value_counts().head(10))

# Power calculations
df['P_FV'] = df['Voltaje_Panel'] * df['Corriente_Panel']
df['P_mot'] = df['Voltaje_Bateria'] * df['Corriente_Motor'].abs()

df['I_mot_regen'] = df['Corriente_Motor'].apply(lambda x: x if x > 0 else 0)
df['I_mot_drive'] = df['Corriente_Motor'].apply(lambda x: abs(x) if x < 0 else 0)
df['P_mot_drive'] = df['Voltaje_Bateria'] * df['I_mot_drive']
df['P_regen'] = df['Voltaje_Bateria'] * df['I_mot_regen']

# Energy integration
E_FV_wh = (df['P_FV'] * df['dt']).sum() / 3600.0
E_mot_wh = (df['P_mot'] * df['dt']).sum() / 3600.0
E_drive_wh = (df['P_mot_drive'] * df['dt']).sum() / 3600.0
E_regen_wh = (df['P_regen'] * df['dt']).sum() / 3600.0

print("\n=== INTEGRATED ENERGY RESULTS ===")
print(f"E_FV (Solar Generated): {E_FV_wh:.2f} Wh")
print(f"E_mot_total (|I_mot|*V_bat): {E_mot_wh:.2f} Wh")
print(f"E_drive (Traction Demand): {E_drive_wh:.2f} Wh")
print(f"E_regen (Regenerative Braking): {E_regen_wh:.2f} Wh")

print("\n=== MEAN POWER & STATS ===")
print(f"Mean V_bat: {df['Voltaje_Bateria'].mean():.2f} V (Min: {df['Voltaje_Bateria'].min():.2f}, Max: {df['Voltaje_Bateria'].max():.2f})")
print(f"Mean V_panel: {df['Voltaje_Panel'].mean():.2f} V (Min: {df['Voltaje_Panel'].min():.2f}, Max: {df['Voltaje_Panel'].max():.2f})")
print(f"Mean I_panel: {df['Corriente_Panel'].mean():.2f} A (Min: {df['Corriente_Panel'].min():.2f}, Max: {df['Corriente_Panel'].max():.2f})")
print(f"Mean I_motor: {df['Corriente_Motor'].mean():.2f} A (Min: {df['Corriente_Motor'].min():.2f}, Max: {df['Corriente_Motor'].max():.2f})")
print(f"Mean P_FV: {df['P_FV'].mean():.2f} W (Min: {df['P_FV'].min():.2f}, Max: {df['P_FV'].max():.2f})")
print(f"Mean P_mot: {df['P_mot'].mean():.2f} W (Min: {df['P_mot'].min():.2f}, Max: {df['P_mot'].max():.2f})")

ihf_daily = (E_FV_wh / E_drive_wh) * 100.0
print(f"\nDaily IHF (E_FV / E_drive): {ihf_daily:.2f}%")

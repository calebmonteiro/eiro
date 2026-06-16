import pandas as pd
import numpy as np
import os

def run_cleaning_pipeline(input_path, output_path):
    print(f"🔄 Ingesting Raw Data Asset: {input_path}")
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Missing raw input log file at {input_path}")
        
    df = pd.read_csv(input_path)
    
    # Map the exact, real columns from our high-frequency vehicle files
    target_columns = {
        'time': 'timestamp',
        'Engine RPM (rpm)': 'rpm',
        'Vehicle speed (mph)': 'speed_mph',
        'Engine coolant temperature (℃)': 'coolant_temp_c',
        'Vehicle acceleration (g)': 'acceleration_g',
        'Latitude': 'latitude',
        'Longtitude': 'longitude'
    }
    
    # Filter and rename columns safely
    available_cols = [col for col in target_columns.keys() if col in df.columns]
    df_filtered = df[available_cols].rename(columns={k: v for k, v in target_columns.items() if k in available_cols})
    
    # Clean asynchronous sensor streams via Time-Series Forward-Fill / Backward-Fill
    print("🧹 Aligning asynchronous sensor streams via Time-Series Forward Fill...")
    if 'rpm' in df_filtered.columns:
        df_filtered['rpm'] = df_filtered['rpm'].ffill().bfill()
    if 'speed_mph' in df_filtered.columns:
        df_filtered['speed_mph'] = df_filtered['speed_mph'].ffill().bfill()
    if 'coolant_temp_c' in df_filtered.columns:
        df_filtered['coolant_temp_c'] = df_filtered['coolant_temp_c'].ffill().bfill()
    if 'acceleration_g' in df_filtered.columns:
        df_filtered['acceleration_g'] = df_filtered['acceleration_g'].fillna(0.0)
        
    # Drop rows missing critical geospatial coordinate anchors
    df_filtered = df_filtered.dropna(subset=['latitude', 'longitude'])
    
    # Feature Engineering: Group travel rows into categorical driving zones vectorially
    if 'speed_mph' in df_filtered.columns:
        df_filtered['driving_zone'] = pd.cut(
            df_filtered['speed_mph'],
            bins=[-1, 1, 45, 120],
            labels=['idle', 'city', 'highway']
        ).astype(str)
        
    # Ensure staging directory structure exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_filtered.to_csv(output_path, index=False)
    print(f"✅ Staging Layer Saved to: {output_path} ({len(df_filtered)} rows generated)")
    return df_filtered

if __name__ == "__main__":
    raw_file = "data/raw/2026-06-04 08-13-58.csv" 
    output_file = "data/cleaned/june_04_clean.csv"
    run_cleaning_pipeline(raw_file, output_file)

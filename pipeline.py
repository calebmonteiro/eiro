import pandas as pd
import numpy as np

def analyze_commute(input_file):
    print(f"Reading telemetry log: {input_file}...")
    df = pd.read_csv(input_file)
    
    # --- PHASE 1: DATA CLEANING ---
    # Fix wireless dropouts using forward-fill (use the last known good value)
    df['speed'] = df['speed'].ffill()
    
    # Smooth speed changes using a rolling 5-second average
    df['speed_smooth'] = df['speed'].rolling(window=5, min_periods=1).mean()
    
    # --- PHASE 2: JOURNEY SEGMENTATION ---
    # Automatically segment by timestamps (0-5 mins, 5-15 mins, 15-20 mins)
    # Once you use real GPS data, we can swap this for coordinates!
    total_seconds = len(df)
    
    conditions = [
        (df.index < 300),
        (df.index >= 300) & (df.index < 900),
        (df.index >= 900)
    ]
    segments = ['Origin City', 'Highway', 'Destination City']
    df['trip_segment'] = np.select(conditions, segments, default='Highway')
    
    # --- PHASE 3: DRILL-DOWN ANALYTICS ---
    # 1. Total Trip Duration
    total_duration_min = total_seconds / 60
    
    # 2. Average Speeds per segment
    avg_speeds = df.groupby('trip_segment')['speed_smooth'].mean()
    
    # 3. Time Spent Waiting at Signals (Speed is 0, engine load is low idling)
    signal_wait_time_sec = len(df[(df['speed_smooth'] < 1) & (df['engine_load'] < 20)])
    signal_wait_min = signal_wait_time_sec / 60
    
    # 4. Time Lost Behind Racing Trucks (On Highway, Speed stuck between 45-55, high load)
    truck_stuck_sec = len(df[
        (df['trip_segment'] == 'Highway') & 
        (df['speed_smooth'] >= 45) & (df['speed_smooth'] <= 55) & 
        (df['engine_load'] > 50)
    ])
    truck_stuck_min = truck_stuck_sec / 60
    
    # 5. Speed Consistency (Standard Deviation - lower means smoother driving)
    speed_consistency = df.groupby('trip_segment')['speed_smooth'].std()
    
    # --- PHASE 4: PRINT THE PERFORMANCE REPORT ---
    print("\n" + "="*45)
    print("        POST-DRIVE PERFORMANCE REPORT        ")
    print("="*45)
    print(f"Total Completed Drive Time : {total_duration_min:.1f} minutes")
    print(f"Time Wasted At Signals     : {signal_wait_min:.1f} minutes")
    print(f"Time Delayed Behind Trucks : {truck_stuck_min:.1f} minutes")
    print("-"*45)
    
    print("Segment Metrics:")
    for seg in segments:
        print(f"\n📈 **{seg}**")
        print(f"   • Avg Speed: {avg_speeds[seg]:.1f} mph")
        print(f"   • Consistency (StdDev): {speed_consistency[seg]:.1f} (Lower = Smoother)")
        
    # Save the processed data layer
    df.to_csv("data/cleaned/processed_commute.csv", index=False)
    print("\nCleaned analytics file saved to data/cleaned/processed_commute.csv!")

if __name__ == "__main__":
    analyze_commute("data/raw/mock_commute.csv")
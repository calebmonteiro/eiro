import pandas as pd
import numpy as np
import time
import os

def generate_mock_trip():
    np.random.seed(42)
    total_seconds = 1200  # 20-minute drive
    timestamps = time.time() + np.arange(total_seconds)
    
    # Simulate a 3-part journey profile
    # 0-300s: City Origin, 300-900s: Highway, 900-1200s: City Destination
    speeds = []
    throttle_positions = []
    coolant_temps = []
    engine_loads = []
    
    current_temp = 70.0 # Starts slightly cool
    
    for t in range(total_seconds):
        # Update engine temp gradually until it stabilizes around 90C
        if current_temp < 90:
            current_temp += 0.05 + np.random.uniform(-0.01, 0.01)
        else:
            current_temp += np.random.uniform(-0.2, 0.2)
        coolant_temps.append(round(current_temp, 1))
        
        # Segment 1: City Origin (0 to 5 mins) -> Stop & go, traffic lights
        if t < 300:
            if 100 <= t <= 140: # Stopped at a red light
                speed = 0
                throttle = 0
                load = 15.0
            else: # Creeping/driving in city
                speed = 30 + np.sin(t/10) * 10 + np.random.uniform(-3, 3)
                throttle = 18 + np.sin(t/10) * 5
                load = 35.0 + np.random.uniform(-5, 5)
                
        # Segment 2: Highway (5 to 15 mins) -> High speed, one truck delay
        elif 300 <= t < 900:
            if 500 <= t <= 650: # Stuck behind two racing trucks!
                speed = 52 + np.random.uniform(-1, 1) # Forced down from highway speeds
                throttle = 35 # Stepping on it out of frustration
                load = 65.0 # Engine straining at lower speed
            else: # Free-flow highway cruising
                speed = 70 + np.random.uniform(-2, 2)
                throttle = 22 + np.random.uniform(-2, 2)
                load = 40.0 + np.random.uniform(-3, 3)
                
        # Segment 3: City Destination (15 to 20 mins) -> Slowing down, final stop
        else:
            if t > 1150: # Parked at work
                speed = 0
                throttle = 0
                load = 15.0
            else:
                speed = 25 + np.cos(t/15) * 12 + np.random.uniform(-4, 4)
                throttle = 15 + np.random.uniform(-3, 3)
                load = 30.0 + np.random.uniform(-6, 6)
                
        speeds.append(max(0, speed))
        throttle_positions.append(max(0, throttle))
        engine_loads.append(max(15.0, load))

    # Generate dummy coordinates moving roughly from one point to another
    lats = np.linspace(40.0000, 40.1500, total_seconds) + np.random.uniform(-0.0001, 0.0001, total_seconds)
    lons = np.linspace(-83.0000, -83.1000, total_seconds) + np.random.uniform(-0.0001, 0.0001, total_seconds)

    df = pd.DataFrame({
        'timestamp': timestamps,
        'gps_lat': lats,
        'gps_lon': lons,
        'speed': speeds,
        'throttle_pos': throttle_positions,
        'engine_load': engine_loads,
        'coolant_temp': coolant_temps
    })
    
    # Introduce a few random dropouts (NaNs) to simulate real BLE wireless blips
    df.loc[df.sample(frac=0.01).index, 'speed'] = np.nan
    
    output_path = "data/raw/mock_commute.csv"
    df.to_csv(output_path, index=False)
    print(f"🎉 Success! Mock commute file generated at: {output_path}")

if __name__ == "__main__":
    generate_mock_trip()
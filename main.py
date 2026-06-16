import obd
import pandas as pd
import csv
import time
import threading
from datetime import datetime

# ── Settings ──────────────────────────────────────────────
POLL_INTERVAL = 0.5          # read sensors every 0.5 seconds
OUTPUT_FOLDER = "data/raw"   # where your drive CSVs get saved

# ── Sensors to record ─────────────────────────────────────
SENSORS = [
    obd.commands.RPM,
    obd.commands.SPEED,
    obd.commands.COOLANT_TEMP,
    obd.commands.THROTTLE_POS,
    obd.commands.ENGINE_LOAD,
    obd.commands.INTAKE_TEMP,
    obd.commands.MAF,
]

# ── File setup ────────────────────────────────────────────
import os
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M")
filename  = f"{OUTPUT_FOLDER}/drive_{timestamp}.csv"
FIELDS    = ["timestamp", "rpm", "speed_kmh", "coolant_temp_c",
             "throttle_pct", "engine_load_pct", "intake_temp_c", "maf_gs"]

# ── Logger ────────────────────────────────────────────────
stop_event = threading.Event()

def read_sensor(connection, cmd):
    """Query one sensor, return its value or None if unavailable."""
    try:
        resp = connection.query(cmd)
        return None if resp.is_null() else resp.value.magnitude
    except Exception:
        return None

def logger_thread(connection):
    print(f"\n Recording to: {filename}")
    print(" Press Ctrl+C to stop.\n")

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        row_count = 0

        while not stop_event.is_set():
            row = {
                "timestamp":        time.time(),
                "rpm":              read_sensor(connection, obd.commands.RPM),
                "speed_kmh":        read_sensor(connection, obd.commands.SPEED),
                "coolant_temp_c":   read_sensor(connection, obd.commands.COOLANT_TEMP),
                "throttle_pct":     read_sensor(connection, obd.commands.THROTTLE_POS),
                "engine_load_pct":  read_sensor(connection, obd.commands.ENGINE_LOAD),
                "intake_temp_c":    read_sensor(connection, obd.commands.INTAKE_TEMP),
                "maf_gs":           read_sensor(connection, obd.commands.MAF),
            }
            writer.writerow(row)
            f.flush()       # write immediately — no data lost on Ctrl+C
            row_count += 1
            print(f"  Row {row_count:>4} | RPM: {row['rpm']:>6} | "
                  f"Speed: {row['speed_kmh']:>5} | Temp: {row['coolant_temp_c']}", end="\r")
            time.sleep(POLL_INTERVAL)

    print(f"\n\n Done. {row_count} rows saved to {filename}")

# ── Main ──────────────────────────────────────────────────
def main():
    print("Connecting to your Civic...")
    connection = obd.OBD()          # auto-detects the dongle over Bluetooth

    if not connection.is_connected():
        print("\n Could not connect. Make sure:")
        print("  1. Dongle is plugged into the OBD port")
        print("  2. Dongle is paired in Windows Bluetooth settings")
        print("  3. Engine is on (or key in position II)")
        return

    print(f" Connected! Found {len(connection.supported_commands)} supported sensors.")

    t = threading.Thread(target=logger_thread, args=(connection,), daemon=True)
    t.start()

    try:
        while t.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n Stopping logger...")
        stop_event.set()
        t.join()
        connection.close()

if __name__ == "__main__":
    main()
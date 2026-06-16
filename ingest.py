import os
import sqlite3
from datetime import datetime

import pandas as pd


DB_PATH = "database/civic.db"
DEFAULT_VEHICLE = ("Honda", "Civic", 2008)
DRIVING_ZONES = ("idle", "city", "highway")


def create_star_schema(conn: sqlite3.Connection) -> None:
    """Create dimension and fact tables for the telematics star schema."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dim_vehicle (
            vehicle_id   INTEGER PRIMARY KEY,
            make         TEXT NOT NULL,
            model        TEXT NOT NULL,
            year         INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dim_driving_zone (
            zone_id      INTEGER PRIMARY KEY,
            zone_name    TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS dim_date (
            date_id      INTEGER PRIMARY KEY,
            full_date    TEXT NOT NULL UNIQUE,
            year         INTEGER NOT NULL,
            month        INTEGER NOT NULL,
            day          INTEGER NOT NULL,
            day_of_week  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dim_time (
            time_id      INTEGER PRIMARY KEY,
            hour         INTEGER NOT NULL,
            minute       INTEGER NOT NULL,
            second       INTEGER NOT NULL,
            millis       INTEGER NOT NULL,
            UNIQUE (hour, minute, second, millis)
        );

        CREATE TABLE IF NOT EXISTS fact_telemetry (
            telemetry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id       INTEGER NOT NULL,
            date_id          INTEGER NOT NULL,
            time_id            INTEGER NOT NULL,
            zone_id          INTEGER NOT NULL,
            rpm              REAL,
            speed_mph        REAL,
            coolant_temp_c   REAL,
            acceleration_g   REAL,
            latitude         REAL NOT NULL,
            longitude        REAL NOT NULL,
            event_timestamp  TEXT NOT NULL,
            FOREIGN KEY (vehicle_id) REFERENCES dim_vehicle(vehicle_id),
            FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
            FOREIGN KEY (time_id) REFERENCES dim_time(time_id),
            FOREIGN KEY (zone_id) REFERENCES dim_driving_zone(zone_id)
        );

        CREATE INDEX IF NOT EXISTS idx_fact_telemetry_date
            ON fact_telemetry(date_id);
        CREATE INDEX IF NOT EXISTS idx_fact_telemetry_zone
            ON fact_telemetry(zone_id);
        CREATE INDEX IF NOT EXISTS idx_fact_telemetry_timestamp
            ON fact_telemetry(event_timestamp);
        """
    )


def seed_dimensions(conn: sqlite3.Connection) -> int:
    """Populate static dimension tables and return the vehicle_id."""
    make, model, year = DEFAULT_VEHICLE
    conn.execute(
        "INSERT OR IGNORE INTO dim_vehicle (vehicle_id, make, model, year) VALUES (1, ?, ?, ?)",
        (make, model, year),
    )

    for zone_id, zone_name in enumerate(DRIVING_ZONES, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO dim_driving_zone (zone_id, zone_name) VALUES (?, ?)",
            (zone_id, zone_name),
        )

    return 1


def _get_or_create_date_id(conn: sqlite3.Connection, drive_date: str) -> int:
    row = conn.execute(
        "SELECT date_id FROM dim_date WHERE full_date = ?", (drive_date,)
    ).fetchone()
    if row:
        return row[0]

    parsed = datetime.strptime(drive_date, "%Y-%m-%d")
    conn.execute(
        """
        INSERT INTO dim_date (full_date, year, month, day, day_of_week)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            drive_date,
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.strftime("%A"),
        ),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _get_or_create_time_id(conn: sqlite3.Connection, time_value: str) -> int:
    parsed = datetime.strptime(time_value, "%H:%M:%S.%f")
    hour, minute, second, millis = (
        parsed.hour,
        parsed.minute,
        parsed.second,
        parsed.microsecond // 1000,
    )

    row = conn.execute(
        """
        SELECT time_id FROM dim_time
        WHERE hour = ? AND minute = ? AND second = ? AND millis = ?
        """,
        (hour, minute, second, millis),
    ).fetchone()
    if row:
        return row[0]

    conn.execute(
        """
        INSERT INTO dim_time (hour, minute, second, millis)
        VALUES (?, ?, ?, ?)
        """,
        (hour, minute, second, millis),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _get_zone_id(conn: sqlite3.Connection, zone_name: str) -> int:
    row = conn.execute(
        "SELECT zone_id FROM dim_driving_zone WHERE zone_name = ?", (zone_name,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown driving zone: {zone_name}")
    return row[0]


def ingest_cleaned_csv(
    csv_path: str,
    db_path: str = DB_PATH,
    drive_date: str = "2026-06-04",
    clear_existing: bool = True,
) -> int:
    """
    Load a cleaned staging CSV into the SQLite star schema.

    Returns the number of fact rows inserted.
    """
    print(f"📥 Loading staging file: {csv_path}")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing cleaned CSV at {csv_path}")

    df = pd.read_csv(csv_path)
    required_columns = {
        "timestamp",
        "latitude",
        "longitude",
        "driving_zone",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Cleaned CSV is missing required columns: {sorted(missing)}")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        create_star_schema(conn)
        vehicle_id = seed_dimensions(conn)
        date_id = _get_or_create_date_id(conn, drive_date)

        if clear_existing:
            conn.execute("DELETE FROM fact_telemetry")

        zone_cache = {
            zone: _get_zone_id(conn, zone)
            for zone in df["driving_zone"].dropna().unique()
        }
        time_cache: dict[str, int] = {}

        fact_rows = []
        for _, row in df.iterrows():
            time_key = str(row["timestamp"])
            if time_key not in time_cache:
                time_cache[time_key] = _get_or_create_time_id(conn, time_key)

            event_timestamp = f"{drive_date} {time_key}"
            fact_rows.append(
                (
                    vehicle_id,
                    date_id,
                    time_cache[time_key],
                    zone_cache[row["driving_zone"]],
                    row.get("rpm"),
                    row.get("speed_mph"),
                    row.get("coolant_temp_c"),
                    row.get("acceleration_g"),
                    row["latitude"],
                    row["longitude"],
                    event_timestamp,
                )
            )

        conn.executemany(
            """
            INSERT INTO fact_telemetry (
                vehicle_id, date_id, time_id, zone_id,
                rpm, speed_mph, coolant_temp_c, acceleration_g,
                latitude, longitude, event_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            fact_rows,
        )
        conn.commit()

    print(f"✅ Star schema loaded: {len(fact_rows)} rows → {db_path}")
    return len(fact_rows)


if __name__ == "__main__":
    cleaned_file = "data/cleaned/june_04_clean.csv"
    ingest_cleaned_csv(cleaned_file)

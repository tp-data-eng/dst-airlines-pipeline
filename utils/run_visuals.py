import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from sqlalchemy import create_engine, text

# =========================================================================
# PATH CONFIGURATION
# =========================================================================
# Anchor to the directory containing main_pipeline.py (etl_pipeline/)
BASE_DIR = Path(__file__).resolve().parent

# Define Project Root
PROJECT_ROOT = BASE_DIR.parent

# Add PROJECT_ROOT to Python's search path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================================
# IMPORTS
# =========================================================================
from utils.data_analysis import AirlineVisualizer


# =========================================================================
# DATABASE & OUTPUT CONFIGURATION
# =========================================================================
DB_PATH = PROJECT_ROOT / 'database' / 'airlines_warehouse.db'
OUTPUTS_DIR = PROJECT_ROOT / 'outputs'


# =========================================================================
# SQL QUERIES
# =========================================================================
QUERY_MAX_TELEMETRY = text("""
    SELECT MAX(updated_date_key), updated_time_key
    FROM fact_flight
    WHERE updated_date_key = (SELECT MAX(updated_date_key) FROM fact_flight);
""")

QUERY_HUB_AIRLINES = """
    SELECT f.dep_icao AS hub_airport, a.airline_name
    FROM fact_flight f
    JOIN dim_airline a ON f.airline_icao = a.icao_code
    WHERE f.dep_icao IN ('EGLL', 'LTFM', 'LFPG')
    UNION ALL
    SELECT f.arr_icao AS hub_airport, a.airline_name
    FROM fact_flight f
    JOIN dim_airline a ON f.airline_icao = a.icao_code
    WHERE f.arr_icao IN ('EGLL', 'LTFM', 'LFPG');
"""

QUERY_ACTIVE_AIRLINES = """
    SELECT a.airline_name
    FROM fact_flight f
    JOIN dim_airline a ON f.airline_icao = a.icao_code;
"""

QUERY_AIRCRAFT_FLEET = """
    SELECT hex, reg_number, model
    FROM dim_aircraft;
"""


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================
def get_warehouse_data_freshness(conn) -> str:
    """Extracts UTC timestamp from warehouse and converts it to Berlin local time."""
    try:
        row = conn.execute(QUERY_MAX_TELEMETRY).fetchone()
        if not row or not row[0]:
            return "N/A"

        d_str = str(row[0])     # YYYYMMDD

        # Format time_key integer (HHMM -> HH:MM)
        time_key = row[1] if row[1] is not None else 0
        t_str = f"{time_key:04d}"

        # Combine into a UTC datetime object
        utc_dt = datetime(
            year=int(d_str[:4]),
            month=int(d_str[4:6]),
            day = int(d_str[6:]),
            hour = int(t_str[:2]),
            minute = int(t_str[2:]),
            tzinfo = ZoneInfo("UTC")
        )

        # Convert to Berlin time and format with timezone name (CEST/CET)
        berlin_dt = utc_dt.astimezone(ZoneInfo("Europe/Berlin"))
        return berlin_dt.strftime("%Y-%m-%d %H:%M %Z")

    except Exception:
        return "N/A"


# =========================================================================
# MAIN RUNNER
# =========================================================================
def main():
    if not DB_PATH.exists():
        print(f"Error: Warehouse database not found at {DB_PATH}")
        return

    print("Initializing standalone visual report generator...")
    engine = create_engine(f'sqlite:///{DB_PATH.as_posix()}')
    viz = AirlineVisualizer(output_dir = OUTPUTS_DIR)

    with engine.connect() as conn:
        # Fetch Warehouse Data Freshness Timestamp
        data_freshness_str = get_warehouse_data_freshness(conn)
        print(f"Warehouse Data Freshness (Latest Record): {data_freshness_str or 'N/A'}")

        print("\nGenerating static analytical reports...")

        # Scheduled Hub Traffic
        try:
            df_hubs = pd.read_sql(QUERY_HUB_AIRLINES, conn)
            path = viz.plot_top_hub_airlines(
                df_hubs,
                top_n=5,
                data_as_of=data_freshness_str
            )
            print(f" -> Hub traffic report saved: {path}")
        except Exception as e:
            print(f" -> Skipping Hub Traffic Report: {e}")

        # Active Airlines Volume
        try:
            df_active_airlines = pd.read_sql(QUERY_ACTIVE_AIRLINES, conn)
            path = viz.plot_top_airlines(
                df_active_airlines,
                top_n=10,
                data_as_of=data_freshness_str
            )
            print(f" -> Top Airlines Report saved: {path}")
        except Exception as e:
            print(f" -> Skipping Top Airlines Report: {e}")

        # Fleet & Data Quality Audit
        try:
            df_aircraft = pd.read_sql(QUERY_AIRCRAFT_FLEET, conn)

            path_reg = viz.plot_registration_coverage(
                df_aircraft,
                data_as_of=data_freshness_str
            )
            print(f" -> Registration Coverage Report saved: {path_reg}")

            path_audit = viz.plot_fleet_coverage_audit(
                df_aircraft,
                top_n=10,
                data_as_of=data_freshness_str
            )
            print(f" -> Fleet Data Quality Audit saved: {path_audit}")

        except Exception as e:
            print(f" -> Skipping Fleet & Coverage Reports: {e}")

    print("\nReport generation completed! Check /outputs for subfolder reports!")


if __name__ == "__main__":
    main()
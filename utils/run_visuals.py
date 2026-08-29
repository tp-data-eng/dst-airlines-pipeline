import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine

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
# EXECUTION
# =========================================================================
def main():
    db_path = PROJECT_ROOT / 'database' / 'airlines_warehouse.db'
    if not db_path.exists():
        print(f"Error: Warehouse database not found at {db_path}")
        return

    engine = create_engine(f'sqlite:///{db_path.as_posix()}')
    viz = AirlineVisualizer(output_dir = PROJECT_ROOT / 'outputs')

    print("Generating static warehouse reports...")

    with engine.connect() as conn:
        # Registration Coverage & Data Quality Audit
        try:
            df_aircraft = pd.read_sql("SELECT hex, reg_number, model FROM dim_aircraft;", conn)
            viz.plot_registration_coverage(df_aircraft)
            viz.plot_fleet_coverage_audit(df_aircraft, top_n = 10)
            viz.plot_top_aircraft_models(df_aircraft, top_n = 10)
            print(" -> Fleet & Coverage reports rendered.")
        except Exception as e:
            print(f" -> Skipping fleet reports: {e}")

        # Active Airline Volume
        try:
            query_active_airlines = """
                SELECT a.airline_name
                FROM fact_flight f
                JOIN dim_airline a ON f.airline_icao = a.icao_code;
            """
            df_active_airlines = pd.read_sql(query_active_airlines, conn)
            viz.plot_top_airlines(df_active_airlines, top_n = 10)
            print(" -> Top airlines report rendered.")
        except Exception as e:
            print(f" -> Skipping top airlines report: {e}")

        # Scheduled Hub Traffic
        try:
            query_hubs = """
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
            df_hubs = pd.read_sql(query_hubs, conn)
            viz.plot_top_hub_airlines(df_hubs, top_n = 5)
            print(" -> Hub traffic report rendered.")
        except Exception as e:
            print(f" -> Skipping hub traffic report: {e}")

    print("\nAll static reports successfully saved to /outputs subfolders!")


if __name__ == "__main__":
    main()
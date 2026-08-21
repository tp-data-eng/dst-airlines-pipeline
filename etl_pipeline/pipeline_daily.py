import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text


# =========================================================================
# PATH CONFIGURATION
# =========================================================================
# Anchor to the directory containing main_pipeline.py (etl_pipeline/)
BASE_DIR = Path(__file__).resolve().parent

# Define Project Root
PROJECT_ROOT = BASE_DIR.parent

# Inject the project root so it can find the 'utils' folder
sys.path.append(str(PROJECT_ROOT))


# =========================================================================
# LOCAL IMPORTS
# =========================================================================
from utils.map_generator import generate_flight_map
from api_utils import run_batch_ingestion
from pipeline_utils import (
    clean_flights,
    clean_schedules,
    build_fact_flight,
    load_incremental_flights,
    enrich_dim_aircraft,
    enrich_dim_airlines,
    enrich_dim_airports,
)


# =========================================================================
# DATABASE CONFIGURATION
# =========================================================================
DB_NAME = "airlines_warehouse.db"

# Route the files to their designated folders
DB_DEST_DIR = PROJECT_ROOT / "database"
DB_PATH = DB_DEST_DIR / DB_NAME

# Check if the database file already exists
db_exists = DB_PATH.exists()

# Create SQLAlchemy engine connection (using .as_posix() for OS compatibility)
engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")


# =========================================================================
# CONFIGURATION TOGGLES
# =========================================================================
VERBOSE_PIPELINE = False  # Toggle True to see detailed step-by-step pipeline telemetry


# =========================================================================
# DAILY INCREMENTAL RUN (Runs every execution)
# =========================================================================
if not db_exists:
    print("Error: Database does not exist. Please run pipeline_init.py first.")
else:
    print("Starting routine flight & schedule ingestion...")

    # =========================================================================
    # STALE DATA CLEANUP
    try:
        print("Cleaning up stale en-route flights...")
        with engine.begin() as connection:
            # Force-expire anything that hasn't updated recently
            # (Assuming your table has a timestamp column, or let's target old date keys safely)
            cleanup_query = text("""
                    UPDATE fact_flight
                    SET status = 'assumed-landed'
                    WHERE status = 'en-route'
                      AND updated_date_key < strftime('%Y%m%d', 'now', '-2 days');
                """)
            # If your updated_date_key is an integer column, you can calculate the 2-day threshold mathematically:
            # e.g., current YYYYMMDD minus 2 days roughly, or better yet, track via a true datetime column.

            result = connection.execute(cleanup_query)
            print(f"Cleanup: Marked {result.rowcount} stale en-route flights as assumed-landed.")
    except Exception as e:
        print(f"Notice: Stale flight cleanup skipped: {e}")

    # Pull live flights globally (unfiltered)
    df_raw_flights = run_batch_ingestion({'flights': {}}, verbose=VERBOSE_PIPELINE)
    flights_df = df_raw_flights.get('flights')

    # =========================================================================
    # Dynamic Schedule Ingestion
    TARGET_AIRPORTS = ['EGLL', 'LTFM', 'LFPG']

    sched_list = []

    for airport in TARGET_AIRPORTS:
        if VERBOSE_PIPELINE:
            print(f"Fetching schedules for {airport}...")

        # Pull schedules for the specific airport in the loop
        df_raw_sched_dep = run_batch_ingestion({'schedules': {'dep_icao': airport}}, verbose=VERBOSE_PIPELINE)
        df_raw_sched_arr = run_batch_ingestion({'schedules': {'arr_icao': airport}}, verbose=VERBOSE_PIPELINE)

        # Extract DataFrames
        sched_dep_df = df_raw_sched_dep.get('schedules')
        sched_arr_df = df_raw_sched_arr.get('schedules')

        # Append to master list if valid
        if sched_dep_df is not None and not sched_dep_df.empty:
            sched_list.append(sched_dep_df)
        if sched_arr_df is not None and not sched_arr_df.empty:
            sched_list.append(sched_arr_df)

    # Combine all collected schedule results safely into a single DataFrame
    if sched_list:
        combined_schedules = pd.concat(sched_list, ignore_index=True).drop_duplicates()
    else:
        combined_schedules = pd.DataFrame(columns=['flight_icao'])

    print("Schedule Dep Nulls:", combined_schedules['dep_time_utc'].isnull().sum())
    print("Schedule Arr Nulls:", combined_schedules['arr_time_utc'].isnull().sum())

    if flights_df is not None and not flights_df.empty:
        print("Cleaning live telemetry and schedules...")

        # Clean the raw data
        fact_flights, dim_flight_position, df_live_aircraft_patch = clean_flights(flights_df, verbose=VERBOSE_PIPELINE)

        if not combined_schedules.empty:
            clean_scheds = clean_schedules(combined_schedules, verbose=VERBOSE_PIPELINE)
        else:
            # Failsafe, if schedules endpoint returns nothing
            clean_scheds = pd.DataFrame(columns=['flight_icao'])

        # Merge: Attach schedules to the live flights
        final_fact_flights = build_fact_flight(fact_flights, clean_scheds, verbose=VERBOSE_PIPELINE)

        # ================================================
        # Generate Flight Map
        # ================================================
        # Join coordinates with flight details
        map_df = pd.merge(
            dim_flight_position,
            final_fact_flights,
            on="flight_id",
            how="inner"
        )

        # Add the reg_numbers
        map_df = pd.merge(
            map_df,
            df_live_aircraft_patch[['aircraft_hex', 'reg_number']],
            on="aircraft_hex",
            how="left"
        )

        # Pass combined DF to the map
        generate_flight_map(map_df, TARGET_AIRPORTS)

        # ================================================
        # Enrichment 1: Update the aircraft dimension with live patch
        try:
            print("Checking for new aircraft data to enrich dim_aircraft...")
            existing_aircraft = pd.read_sql("SELECT * FROM dim_aircraft;", engine)

            # Get the full, updated DataFrame from enrich_dim_aircraft
            dim_aircraft_enriched = enrich_dim_aircraft(existing_aircraft, df_live_aircraft_patch, verbose=VERBOSE_PIPELINE)

            # Clear the existing data without touching the table schema
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM dim_aircraft;"))

            # Append the full enriched DataFrame back into the empty table
            dim_aircraft_enriched.to_sql('dim_aircraft', engine, if_exists='append', index=False)
            print(f"Aircraft dimension updated successfully with {len(dim_aircraft_enriched)} total records.")

        except Exception as e:
            print(f"Skipping aircraft enrichment due to error: {e}")

        # ================================================
        # Enrichment 2: Update the aircraft dimension with live patch
        try:
            print("Checking live flights to patch missing Airline data...")
            existing_airlines = pd.read_sql("SELECT * FROM dim_airline;", engine)

            # Get the full, updated DataFrame
            dim_airline_enriched = enrich_dim_airlines(existing_airlines, flights_df, verbose=VERBOSE_PIPELINE)

            # Clear existing data
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM dim_airline;"))

            # Append the full enriched DataFrame
            dim_airline_enriched.to_sql('dim_airline', engine, if_exists='append', index=False)
            print("Airline dimension updated successfully.")

        except Exception as e:
            print(f"Skipping aircraft enrichment due to error: {e}")

        # ================================================
        # Enrichment 3: Update the airport dimension with live patch
        try:
            print("Checking live flights to patch missing Airport IATA data...")
            existing_airports = pd.read_sql("SELECT * FROM dim_airport;", engine)

            # Get the full, updated DataFrame
            dim_airport_enriched = enrich_dim_airports(existing_airports, flights_df, verbose=VERBOSE_PIPELINE)

            # Clear existing data
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM dim_airport;"))

            # Append the full enriched DataFrame
            dim_airport_enriched.to_sql('dim_airport', engine, if_exists='append', index=False)
            print("Airport dimension updated successfully.")

        except Exception as e:
            print(f"Skipping airport enrichment due to error: {e}")

        # =========================================================================
        # DATABASE LOAD
        print("Pushing incremental data to the data warehouse...")
        added_flights, added_telemetry = load_incremental_flights(engine, final_fact_flights, dim_flight_position, verbose=VERBOSE_PIPELINE)

        print("Pipeline run completed successfully!")
        print(f"Audit: Added {added_flights} new flights and {added_telemetry} telemetry points.")

    else:
        print("No flight data returned from API today. Pipeline aborted.")
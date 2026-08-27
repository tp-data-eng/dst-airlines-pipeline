from pathlib import Path
import sys


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
import pandas as pd
from sqlalchemy import create_engine, text
from api_utils import run_batch_ingestion
from pipeline_utils import (
    clean_countries_db,
    clean_cities_db,
    clean_airports_db,
    clean_airlines_db,
    clean_aircraft_db,
    ingest_aircraft_paginated
)
from utils.data_analysis import AirlineVisualizer

# Initialize visualizer
viz = AirlineVisualizer(output_dir=PROJECT_ROOT / "outputs")


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
# MONTHLY REFRESH EXECUTION
# =========================================================================
if not db_exists:
    print("Error: Database does not exist. Please run pipeline_init.py first.")
else:
    print("Starting monthly static database check and refresh...")

    # Define endpoints and their specific requirements
    monthly_plan = {
        'airportsDB': {},
        'airlinesDB': {},
        'citiesDB': {},
        'countriesDB': {},
    }

    print("Ingesting fresh reference datasets from AirLabs API...")
    df = run_batch_ingestion(monthly_plan, verbose=VERBOSE_PIPELINE)

    if VERBOSE_PIPELINE:
        print("\nCleaning updated reference datasets...")

    dim_countries = clean_countries_db(df['countriesDB'], verbose=VERBOSE_PIPELINE)
    dim_cities = clean_cities_db(df['citiesDB'], verbose=VERBOSE_PIPELINE)
    dim_airports = clean_airports_db(df['airportsDB'], verbose=VERBOSE_PIPELINE)
    dim_airlines = clean_airlines_db(df['airlinesDB'], verbose=VERBOSE_PIPELINE)
#    dim_aircrafts = clean_aircraft_db(df['fleetsDB'], verbose=VERBOSE_PIPELINE)

    # =========================================================================
    # Safeguard 1: dim_airport (Protect daily IATA patches)
    print("Merging monthly airport data safely...")
    existing_airports = pd.read_sql("SELECT * FROM dim_airport;", engine)

    merged_airports = pd.merge(
        dim_airports,
        existing_airports[['icao_code', 'iata_code']],
        on='icao_code',
        how='left',
        suffixes=('', '_existing')
    )

    mask_airport = (
        (merged_airports['iata_code'].isnull() | (merged_airports['iata_code'] == '000')) &
        (merged_airports['iata_code_existing'].notnull()) &
        (merged_airports['iata_code_existing'] != '000')
    )
    merged_airports.loc[mask_airport, 'iata_code'] = merged_airports.loc[mask_airport, 'iata_code_existing']

    # Receipt metric
    airport_enriched_count = mask_airport.sum()
    print(f"-> Successfully preserved and enriched {airport_enriched_count} airport IATA codes.")

    dim_airports_final = merged_airports.drop(columns=['iata_code_existing'], errors='ignore')

    # =========================================================================
    # Safeguard 2: dim_airline (Protect daily IATA & flag patches)
    print("Merging monthly airline data safely...")
    existing_airlines = pd.read_sql("SELECT * FROM dim_airline;", engine)

    merged_airlines = pd.merge(
        dim_airlines,
        existing_airlines[['icao_code', 'iata_code', 'country_code']],
        on='icao_code',
        how='left',
        suffixes=('', '_existing')
    )

    # Protect IATA codes from being downgraded to '000' or null
    mask_airline_iata = (
        (merged_airlines['iata_code'].isnull() | (merged_airlines['iata_code'] == '000')) &
        (merged_airlines['iata_code_existing'].notnull()) &
        (merged_airlines['iata_code_existing'] != '000')
    )
    merged_airlines.loc[mask_airline_iata, 'iata_code'] = merged_airlines.loc[mask_airline_iata, 'iata_code_existing']

    # Protect country codes (flags) from being wiped out
    mask_airline_country = (
            merged_airlines['country_code'].isnull() &
            merged_airlines['country_code_existing'].notnull()
    )
    merged_airlines.loc[mask_airline_country, 'country_code'] = merged_airlines.loc[mask_airline_country, 'country_code_existing']

    # Receipt metric
    airline_enriched_count = mask_airline_iata.sum() + mask_airline_country.sum()
    print(f"-> Successfully preserved and enriched {airline_enriched_count} airline records (IATA/Country).")

    dim_airlines_final = merged_airlines.drop(columns=['iata_code_existing', 'country_code_existing'], errors='ignore')

    # =========================================================================
    # Safeguard 3: dim_aircraft (Protect live hexes & update reference data)
    print("Running paginated fleet ingestion...")

    try:
        ingest_aircraft_paginated(
            engine=engine,
            endpoint_key='fleetsDB',
            max_pages=10,
            limit=50,
            verbose=VERBOSE_PIPELINE
        )
    except Exception as e:
        print(f"Notice: Paginated aircraft ingestion issue: {e}")

    # Run data health audit
    dim_aircraft_df = pd.read_sql("SELECT * FROM dim_aircraft;", engine)
    viz.plot_fleet_coverage_audit(dim_aircraft_df, top_n = 10)

    # =========================================================================
    print("Clearing existing reference records from database...")
    with engine.begin() as conn:
        # Delete old static records safely (CAUTION: dim_aircraft is intentionally EXCLUDED here)
        conn.execute(text("DELETE FROM dim_country;"))
        conn.execute(text("DELETE FROM dim_city;"))
        conn.execute(text("DELETE FROM dim_airport;"))
        conn.execute(text("DELETE FROM dim_airline;"))

    print("Loading fresh reference dimension tables into the database...")
    dim_countries.to_sql('dim_country', engine, if_exists='append', index=False)
    dim_cities.to_sql('dim_city', engine, if_exists='append', index=False)
    dim_airports_final.to_sql('dim_airport', engine, if_exists='append', index=False)
    dim_airlines_final.to_sql('dim_airline', engine, if_exists='append', index=False)

    print("Monthly static databases checked and refreshed successfully!")
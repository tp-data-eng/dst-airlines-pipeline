import pandas as pd
from sqlalchemy import create_engine, text
from api_utils import run_batch_ingestion
import time

# =========================================================================
def clean_airlines_db(df, verbose=False):
    """
    Cleans raw airline data from the AirLabs API and formats it for the DIM_AIRLINES dimension table.

    Args:
        df (pd.DataFrame): Raw airline DataFrame ingested from the API.
        verbose (bool): If True, prints intermediate processing statistics and row counts.

    Returns:
        pd.DataFrame: Cleaned and deduplicated DataFrame ready for DIM_AIRLINES loading.
    """
    original_count = len(df)

    # Only keep rows with the primary ID (ICAO)
    cleaned_df = df.dropna(subset=['icao_code']).copy()
    count_icao_nonnull = len(cleaned_df)

    # Standardize: Fill remaining single-column nulls in 'iata_code' with '000'
    # This prevents 'NULL' from breaking joins in our SQL database
    cleaned_df['iata_code'] = cleaned_df['iata_code'].fillna('000')

    ## Deduplication
    # Make sure every row is a unique airline, by using the Primary Key (icao_code).
    cleaned_df = cleaned_df.drop_duplicates(subset=['icao_code'])

    # Rename Columns (Map 'name' to 'airline_name' and 'flag' to 'country_code')
    rename_cols = {'name': 'airline_name'}
    if 'flag' in cleaned_df.columns:
        rename_cols['flag'] = 'country_code'

    cleaned_df = cleaned_df.rename(columns=rename_cols)

    # Fill remaining text nulls safely
    cleaned_df['airline_name'] = cleaned_df['airline_name'].fillna('UNKNOWN_AIRLINE')

    # Ensure country_code exists and handle NaNs for SQL foreign key compliance
    if 'country_code' in cleaned_df.columns:
        cleaned_df['country_code'] = cleaned_df['country_code'].str.upper()
        # Convert NaNs to None so SQL inserts actual NULLs rather than string 'NaN'
        cleaned_df['country_code'] = cleaned_df['country_code'].where(cleaned_df['country_code'].notnull(), None)
    else:
        cleaned_df['country_code'] = None

    ## Finalize: Select only the columns that we need in our clean dimension table
    final_cols = ['icao_code', 'iata_code', 'airline_name', 'country_code']
    dim_airlines = cleaned_df[final_cols].copy()

    if verbose:
        print(f"Original records from /airlines: {original_count}")
        print(f"Count after keeping non-null 'icao_code' rows: {count_icao_nonnull}")
        print(f"Final unique airline records for DIM_AIRLINES: {len(dim_airlines)}")

    return dim_airlines


# =========================================================================
def clean_airports_db(df, verbose=False):
    """
    Cleans raw airport data from the AirLabs API and formats it for the DIM_AIRPORT dimension table.

    Args:
        df (pd.DataFrame): Raw airport DataFrame ingested from the API.
        verbose (bool): If True, prints intermediate processing statistics and row counts.

    Returns:
        pd.DataFrame: Cleaned and deduplicated DataFrame ready for DIM_AIRPORT loading.
    """
    original_count = len(df)

    cleaned_df = df.dropna(subset=['icao_code', 'lat', 'lng']).copy()
    cleaned_df = cleaned_df.drop_duplicates(subset=['icao_code'])
    cleaned_df['iata_code'] = cleaned_df['iata_code'].fillna('000').astype(str)

    cleaned_df = cleaned_df.rename(columns={
        'name': 'airport_name',
        'lat': 'latitude',
        'lng': 'longitude',
    })

    final_cols = ['airport_name', 'icao_code', 'iata_code', 'latitude', 'longitude', 'country_code']
    dim_airports = cleaned_df[final_cols].copy()

    if verbose:
        print(f"Original records from /airports: {original_count}")
        print(f"Unique airports for DIM_AIRPORT: {len(dim_airports)}")

    return dim_airports


# =========================================================================
def clean_aircraft_db(df, verbose=False):
    """
    Cleans raw fleet data from the AirLabs API and formats it for the DIM_AIRCRAFT dimension table.

    Args:
        df (pd.DataFrame): Raw fleet/aircraft DataFrame ingested from the API.
        verbose (bool): If True, prints intermediate processing statistics and row counts.

    Returns:
        pd.DataFrame: Cleaned and deduplicated DataFrame ready for DIM_AIRCRAFT loading.
    """
    original_count = len(df)

    # Drop rows where hex is null (= Primary Key of dim_aircraft)
    cleaned_df = df.dropna(subset=['hex']).copy()

    # Safely handle columns that might be missing from the API response
    if 'airline_icao' not in cleaned_df.columns:
        cleaned_df['airline_icao'] = '000'
    else:
        cleaned_df['airline_icao'] = cleaned_df['airline_icao'].fillna('000')

    # Fill missing reg_number, aircraft_icao and aircraft_iata with placeholder
    cleaned_df['reg_number'] = cleaned_df['reg_number'].fillna('UNKNOWN_REG')
    cleaned_df['icao'] = cleaned_df['icao'].fillna('000')
    cleaned_df['iata'] = cleaned_df['iata'].fillna('000')

    # Rename Columns
    cleaned_df = cleaned_df.rename(columns={
        'icao': 'icao_code',
        'iata': 'iata_code'
    })

    # Focus on essential columns (ignore structural noise columns)
    final_cols = ['hex', 'reg_number', 'icao_code', 'iata_code', 'model', 'manufacturer', 'airline_icao']

    # Ensure all final_cols exist to prevent KeyError
    for col in final_cols:
        if col not in cleaned_df.columns:
            cleaned_df[col] = '000'

    # Fixed syntax for dropping duplicates and copying
    dim_aircrafts = cleaned_df[final_cols].drop_duplicates(subset=['hex']).copy()

    if verbose:
        print(f"Original records from /fleets: {original_count}")
        print(f"Unique aircraft records for DIM_AIRCRAFT: {len(dim_aircrafts)}")

    return dim_aircrafts

# =========================================================================

def ingest_aircraft_paginated(engine, endpoint_key = 'fleets', max_pages = 10, limit = 50, verbose = False):
    """
    Loops through the paginated AirLabs fleet endpoint, cleans each batch via clean_aircraft_db,
    and updates dim_aircraft safely in SQLite.
    """
    cleaned_frames = []

    print(f"Starting paginated AirLabs aircraft ingestion (up to {max_pages * limit} records)...")

    for page in range(max_pages):
        offset = page * limit
        ingestion_plan = {
            endpoint_key: {
                'limit': limit,
                'offset': offset
            }
        }

        try:
            # Fetch raw data
            raw_data_dict = run_batch_ingestion(ingestion_plan, verbose = verbose)
            raw_df = raw_data_dict.get(endpoint_key)

            if raw_df is None or raw_df.empty:
                print(f"Page {page + 1}: No records returned. Reached end of API pages.")
                break

            cleaned_df = clean_aircraft_db(raw_df, verbose = verbose)

            if not cleaned_df.empty:
                cleaned_frames.append(cleaned_df)
                if verbose:
                    print(f"Page {page + 1}/{max_pages}: Successfully processed {len(cleaned_df)} records.")

            # Pause to prevent API rate limiting
            time.sleep(0.2)

        except Exception as e:
            print(f"Warning: Failed fetching page {page + 1}: {e}")
            break

    if not cleaned_frames:
        print("Attention: No valid aircraft records were processed.")
        return

    # Combine newly fetched and cleaned batches
    new_fleet_df = pd.concat(cleaned_frames, ignore_index = True).drop_duplicates(subset=['hex'])

    # Merge with existing database records, keep newest fetched values for each hex
    existing_dim = pd.read_sql("SELECT * FROM dim_aircraft;", engine)
    combined_dim = pd.concat([existing_aircraft if 'existing_aircraft' in locals() else existing_dim, new_fleet_df], ignore_index = True)
    combined_dim = combined_dim.drop_duplicates(subset=['hex'], keep = 'last')

    # Overwrite SQLite table safely
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM dim_aircraft;"))
        combined_dim.to_sql('dim_aircraft', conn, if_exists = 'append', index = False)

    print(f"Successfully updated dim_aircraft! Total fleet records now: {len(combined_dim)}")


# =========================================================================
def clean_cities_db(df, verbose=False):
    """
    Cleans raw city data from the AirLabs API and formats it for the DIM_CITY dimension table.

    Args:
        df (pd.DataFrame): Raw city DataFrame ingested from the API.
        verbose (bool): If True, prints intermediate processing statistics and row counts.

    Returns:
        pd.DataFrame: Cleaned and deduplicated DataFrame ready for DIM_CITY loading.
    """
    original_count = len(df)

    cleaned_df = df.drop(columns=['type'], errors='ignore')

    # Rename columns to meet target database schema metrics
    rename_columns = {
        'name': 'city_name',
        'lat': 'latitude',
        'lng': 'longitude'
    }
    cleaned_df = cleaned_df.rename(columns=rename_columns)

    # Standardize country code upper-casing
    if 'country_code' in cleaned_df.columns:
        cleaned_df['country_code'] = cleaned_df['country_code'].str.upper()

    # Drop any record missing the PK (city_code), coordinates, or country_code
    critical_columns = ['city_code', 'latitude', 'longitude', 'country_code']
    cleaned_df = cleaned_df.dropna(subset=critical_columns)
    count_after_dropna = len(cleaned_df)

    # Deduplicate on the primary key column
    dim_cities = cleaned_df.drop_duplicates(subset=['city_code']).copy()

    if verbose:
        print(f"Original records from /citiesDB: {original_count}")
        print(f"Records after dropping NaNs: {count_after_dropna}")
        print(f"Unique cities for DIM_CITIES: {len(dim_cities)}")

    return dim_cities


# =========================================================================
def clean_countries_db(df, verbose=False):
    """
    Cleans raw country data from the AirLabs API and formats it for the DIM_COUNTRIES dimension table.

    Args:
        df (pd.DataFrame): Raw country DataFrame ingested from the API.
        verbose (bool): If True, prints intermediate processing statistics and row counts.

    Returns:
        pd.DataFrame: Cleaned and deduplicated DataFrame ready for DIM_COUNTRIES loading.
    """
    original_count = len(df)
    cleaned_df = df.copy()

    # Rename columns to meet target database schema metrics
    rename_columns = {
        'code': 'country_code_2',   # PK
        'code3': 'country_code_3',
        'name': 'country_name'
    }
    cleaned_df = cleaned_df.rename(columns=rename_columns)

    # Drop rows missing the primary key or critical name fields
    cleaned_df = cleaned_df.dropna(subset=['country_code_2', 'country_name'])

    # Deduplicate on the primary key column
    cleaned_df = cleaned_df.drop_duplicates(subset=['country_code_2'])

    # Standardize primary key string to upper-casing
    cleaned_df['country_code_2'] = cleaned_df['country_code_2'].str.upper()

    if 'country_code_3' in cleaned_df.columns:
        cleaned_df['country_code_3'] = cleaned_df['country_code_3'].str.upper()

    if verbose:
        print(f"Original records from /countries: {original_count}")
        print(f"Unique countries for DIM_COUNTRIES: {len(cleaned_df)}")

    return cleaned_df


# =========================================================================
def clean_schedules(df, verbose=False):
    """
    Cleans raw schedule data from the AirLabs API and formats it for the fact_flight schema.

    Args:
        df (pd.DataFrame): Raw schedule DataFrame ingested from the API.
        verbose (bool): If True, prints intermediate processing statistics and row counts.

    Returns:
        pd.DataFrame: Cleaned and standardized DataFrame ready for fact_flight ingestion.
    """
    original_count = len(df)

    # Define the exact columns to keep
    columns_to_keep = [
        'flight_number',
        'flight_icao',
        'airline_icao',
        'dep_icao',
        'arr_icao',
        'dep_time_utc',
        'dep_actual_utc',
        'arr_time_utc',
        'arr_actual_utc',
        'status',
        'dep_delayed',
        'arr_delayed'
    ]

    # Filter to only keep existing columns
    existing_cols = [col for col in columns_to_keep if col in df.columns]
    df_clean = df[existing_cols].copy()

    # Convert time columns to standard datetime objects
    time_columns = ['dep_time_utc', 'dep_actual_utc', 'arr_time_utc', 'arr_actual_utc']
    for col in time_columns:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')

    # Rename to match fact_flight schema
    df_clean.rename(columns={
        'dep_time_utc': 'scheduled_dep_time',
        'dep_actual_utc': 'actual_dep_time',
        'arr_time_utc': 'scheduled_arr_time',
        'arr_actual_utc': 'actual_arr_time',
        'dep_delayed': 'dep_delayed_min',
        'arr_delayed': 'arr_delayed_min'
    }, inplace=True)

    final_count = len(df_clean)

    if verbose:
        print(f"Original records from /schedules: {original_count}")
        print(f"Cleaned records for fact_flight: {final_count}")

    return df_clean


# =========================================================================
def generate_dim_date(start_date='2026-01-01', end_date='2036-12-31', verbose=False):
    """
    Generates a static dim_date calendar table for dimensional modeling.

    Args:
        start_date (str): Start date string in YYYY-MM-DD format.
        end_date (str): End date string in YYYY-MM-DD format.
        verbose (bool): If True, prints generation statistics and total date count.

    Returns:
        pd.DataFrame: Complete calendar DataFrame with primary key and date attributes.
    """
    # Create a continuous range of dates
    df = pd.DataFrame({'full_date': pd.date_range(start_date, end_date)})

    # Create the primary key as an integer (YYYYMMDD)
    df['date_key'] = df['full_date'].dt.strftime('%Y%m%d').astype(int)

    # Extract standard calendar attributes
    df['year'] = df['full_date'].dt.year
    df['quarter'] = df['full_date'].dt.quarter
    df['month'] = df['full_date'].dt.month
    df['month_name'] = df['full_date'].dt.month_name()
    df['day_of_month'] = df['full_date'].dt.day
    df['day_of_week'] = df['full_date'].dt.dayofweek + 1  # Monday=1, Sunday=7
    df['day_name'] = df['full_date'].dt.day_name()
    df['day_of_year'] = df['full_date'].dt.dayofyear

    # Create boolean/flag columns (1 = True, 0 = False)
    df['is_weekend'] = df['full_date'].dt.dayofweek.isin([5, 6]).astype(int)
    df['is_month_start'] = df['full_date'].dt.is_month_start.astype(int)
    df['is_month_end'] = df['full_date'].dt.is_month_end.astype(int)

    # Reorder columns to put date_key first
    columns = ['date_key', 'full_date'] + [c for c in df.columns if c not in ['date_key', 'full_date']]

    if verbose:
        print(f"Generated dim_date from {start_date} to {end_date}: {len(df)} total days.")

    return df[columns]


# =========================================================================
def generate_dim_time(verbose=False):
    """
    Generates a static dim_time table at the minute grain (1,440 rows).

    Args:
        verbose (bool): If True, prints generation statistics and total row count.

    Returns:
        pd.DataFrame: Minute-level time dimension table with key attributes and shifts.
    """
    times = pd.date_range("00:00:00", "23:59:00", freq="min").time
    df = pd.DataFrame({'time_string': times})

    # Create integer key (e.g. 14:15 becomes 1415)
    df['time_key'] = df['time_string'].apply(lambda x: x.hour * 100 + x.minute)
    df['time_string'] = df['time_string'].astype(str)
    df['hour_24'] = pd.to_datetime(df['time_string'], format='%H:%M:%S').dt.hour
    df['hour_12'] = df['hour_24'].apply(lambda x: x % 12 or 12)
    df['minute'] = pd.to_datetime(df['time_string'], format='%H:%M:%S').dt.minute
    df['am_pm'] = df['hour_24'].apply(lambda x: 'AM' if x < 12 else 'PM')

    def get_shift(hour):
        if 5 <= hour < 12:
            return 'Morning'
        elif 12 <= hour < 17:
            return 'Afternoon'
        elif 17 <= hour < 22:
            return 'Evening'
        else:
            return 'Night'

    df['shift'] = df['hour_24'].apply(get_shift)

    if verbose:
        print(f"Generated dim_time dimension table: {len(df)} minute-grain records.")

    return df[['time_key', 'time_string', 'hour_24', 'hour_12', 'minute', 'am_pm', 'shift']]


# =========================================================================
def clean_flights(df_flights, verbose=False):
    """
    Cleans real-time flight telemetry data and splits it into three components:
    1. fact_flights (parent fact table)
    2. dim_flight_position (child telemetry table linked via flight_id)
    3. df_live_aircraft_patch (extracted aircraft metadata for daily dim_aircraft enrichment)

    Args:
        df_flights (pd.DataFrame): Raw flight telemetry DataFrame ingested from the API.
        verbose (bool): If True, prints intermediate processing statistics and row counts.

    Returns:
        tuple: (fact_flights, dim_flight_position, df_live_aircraft_patch) DataFrames.
    """
    original_count = len(df_flights)
    cleaned_df = df_flights.copy()

    # Generate dimensional date, time keys, and high-precision telemetry string from UNIX timestamp safely
    if 'updated' in cleaned_df.columns:
        dt_obj = pd.to_datetime(cleaned_df['updated'], unit='s', errors='coerce')
        cleaned_df['updated_date_key'] = dt_obj.dt.strftime('%Y%m%d').astype(int)
        cleaned_df['updated_time_key'] = dt_obj.dt.hour * 100 + dt_obj.dt.minute
        telemetry_time_str = dt_obj.dt.strftime('%H%M%S')
    else:
        cleaned_df['updated_date_key'] = 0
        cleaned_df['updated_time_key'] = 0
        telemetry_time_str = "000000"       # Failsafe Default

    # Drop low-density telemetry columns to remove structural noise early
    columns_to_drop = ['squawk', 'v_speed', 'updated']
    cleaned_df = cleaned_df.drop(columns=columns_to_drop, errors='ignore')

    # Rename columns to meet target database schema metrics
    rename_columns = {
        'hex': 'aircraft_hex',
        'lat': 'aircraft_latitude',
        'lng': 'aircraft_longitude',
        'alt': 'aircraft_altitude',
        'dir': 'aircraft_heading',
        'speed': 'aircraft_speed'
    }
    cleaned_df = cleaned_df.rename(columns=rename_columns)

    # Generate Flight Smart Key based on callsign/hex + scheduled/flight date
    base_id = cleaned_df['flight_icao'].fillna(cleaned_df['aircraft_hex']).astype(str)
    flight_date_key = cleaned_df.get('dep_date_key', cleaned_df['updated_date_key'])
    cleaned_df['flight_id'] = base_id + "_" + flight_date_key.astype(str)

    # Extract parent table fact_flights
    fact_cols = [
        'flight_id',
        'flight_number',
        'flight_iata',
        'flight_icao',
        'status',
        'dep_icao',
        'arr_icao',
        'airline_icao',
        'airline_iata',
        'aircraft_hex',

        'updated_date_key',
        'updated_time_key',
    ]
    # Ensure we only select columns that actually exist to prevent KeyErrors
    existing_fact_cols = [col for col in fact_cols if col in cleaned_df.columns]
    fact_flights = cleaned_df[existing_fact_cols].copy()

    # Extract child table dim_flight_position
    position_cols = [
        'flight_id',
        'aircraft_latitude',
        'aircraft_longitude',
        'aircraft_altitude',
        'aircraft_heading',
        'aircraft_speed'
    ]
    dim_flight_position = cleaned_df[position_cols].copy()

    # Generate high-precision unique position key (flight_id + HHMMSS)
    dim_flight_position['position_key'] = (
            dim_flight_position['flight_id'].astype(str) + "_" + telemetry_time_str
    )

    # Reorder columns to put position_key first
    pos_columns = ['position_key'] + [col for col in position_cols if col != 'position_key']
    dim_flight_position = dim_flight_position[pos_columns]

    # Prevent Unique Constraint Crashes
    dim_flight_position = dim_flight_position.drop_duplicates(subset=['position_key']).copy()

    # Extract Live Aircraft Data, to enrich dim_aircraft later on
    aircraft_patch_cols = ['aircraft_hex', 'reg_number', 'aircraft_icao']
    if all(col in cleaned_df.columns for col in aircraft_patch_cols):
        df_live_aircraft_patch = cleaned_df[aircraft_patch_cols].drop_duplicates(subset=['aircraft_hex']).copy()
        df_live_aircraft_patch['reg_number'] = df_live_aircraft_patch['reg_number'].fillna('UNKNOWN_REG')
    else:
        df_live_aircraft_patch = pd.DataFrame()

    if verbose:
        print(f"Original records from /flights: {original_count}")
        print(f"Processed into {len(fact_flights)} fact records, {len(dim_flight_position)} position points, and {len(df_live_aircraft_patch)} aircraft patches.")

    return fact_flights, dim_flight_position, df_live_aircraft_patch


# =========================================================================
def build_fact_flight(fact_flights, df_clean_schedules, verbose=False):
    """
    Merges cleaned live flights and cleaned schedules into the final fact table.

    Args:
        fact_flights (pd.DataFrame): Cleaned live flights parent DataFrame.
        df_clean_schedules (pd.DataFrame): Cleaned schedule DataFrame.
        verbose (bool): If True, prints merging statistics and row counts.

    Returns:
        pd.DataFrame: Final merged fact table matching the warehouse schema.
    """
    original_count = len(fact_flights)

    # Create a date key on schedules to match against live flights by day
    df_sched_work = df_clean_schedules.copy()
    if 'scheduled_dep_time' in df_sched_work.columns:
        df_sched_work['sched_date_key'] = pd.to_datetime(df_sched_work['scheduled_dep_time']).dt.strftime(
            '%Y%m%d').astype(int)
    else:
        df_sched_work['sched_date_key'] = 0

    # Only keep the timing data from schedules
    cols_to_keep_from_schedules = [
        'flight_icao',  # Crucial for joining
        'sched_date_key',
        'scheduled_dep_time',
        'actual_dep_time',
        'scheduled_arr_time',
        'actual_arr_time',
        'dep_delayed_min',
        'arr_delayed_min'
    ]

    # Filter schedules to avoid _x and _y suffix conflicts during merge
    exist_cols = [c for c in cols_to_keep_from_schedules if c in df_sched_work.columns]
    df_sched_subset = df_sched_work[exist_cols].drop_duplicates(subset=['flight_icao', 'sched_date_key'])

    # Left join schedules onto live flights master dataframe
    final_fact_df = pd.merge(
        fact_flights,
        df_sched_subset,
        left_on=['flight_icao', 'updated_date_key'],
        right_on=['flight_icao', 'sched_date_key'],
        how='left'
    )

    # Final safety net: strictly filter the columns to match schema.sql exactly
    final_columns = [
        'flight_id',
        'flight_number',
        'status',
        'dep_delayed_min',
        'arr_delayed_min',
        'updated_date_key',
        'updated_time_key',
        'dep_icao',
        'arr_icao',
        'airline_icao',
        'aircraft_hex',
        'scheduled_dep_time',
        'actual_dep_time',
        'scheduled_arr_time',
        'actual_arr_time'
    ]

    existing_final_cols = [col for col in final_columns if col in final_fact_df.columns]
    final_fact_result = final_fact_df[existing_final_cols].copy()

    if verbose:
        print(f"Merged {original_count} live flight records with schedules.")
        print(f"Final fact_flight rows: {len(final_fact_result)}")

    return final_fact_result


# =========================================================================
def load_incremental_flights(engine, fact_flights, dim_flight_position, verbose=False):
    """
    Loads incremental flight records and position telemetry, inserting new flights
    and updating active states for existing flights.

    Args:
        engine (sqlalchemy.engine.Engine): SQLAlchemy database engine connection.
        fact_flights (pd.DataFrame): Cleaned fact_flight DataFrame.
        dim_flight_position (pd.DataFrame): Cleaned dim_flight_position DataFrame.
        verbose (bool): If True, prints detailed ingestion statistics and row counts.

    Returns:
        tuple: (added_flights_count, added_telemetry_count) representing rows inserted.
    """
    # Check database which flight_ids already exist
    with engine.begin() as conn:
        existing_ids_df = pd.read_sql("SELECT flight_id FROM fact_flight;", conn)
        existing_ids = set(existing_ids_df['flight_id'].tolist())

        existing_pos_df = pd.read_sql("SELECT position_key FROM dim_flight_position;", conn)
        existing_positions = set(existing_pos_df['position_key'].tolist())

    # Split incoming flights into truly new vs. existing active flights to update
    mask_new = ~fact_flights['flight_id'].isin(existing_ids)
    new_facts = fact_flights[mask_new].drop_duplicates(subset=['flight_id'])
    existing_facts = fact_flights[~mask_new].drop_duplicates(subset=['flight_id'])

    # Filter position telemetry to only append unseen points
    new_positions = dim_flight_position[~dim_flight_position['position_key'].isin(existing_positions)]
    new_positions = new_positions.drop_duplicates(subset=['position_key'])

    inserted_flights_count = len(new_facts)
    updated_flights_count = len(existing_facts)
    added_telemetry_count = len(new_positions)

    # Insert new flights
    if not new_facts.empty:
        new_facts.to_sql('fact_flight', engine, if_exists='append', index=False)
        if verbose:
            print(f"Inserted {len(new_facts)} brand new flights.")

    # Update existing active flights with latest telemetry status/timestamps
    if not existing_facts.empty:
        with engine.begin() as conn:
            for _, row in existing_facts.iterrows():
                update_query = text("""
                    UPDATE fact_flight
                    SET status = :status,
                        updated_date_key = :updated_date_key,
                        updated_time_key = :updated_time_key
                    WHERE flight_id = :flight_id;
                """)
                conn.execute(update_query, {
                    "status": row.get('status', 'en-route'),
                    "updated_date_key": row.get('updated_date_key', 0),
                    "updated_time_key": row.get('updated_time_key', 0),
                    "flight_id": row['flight_id']
                })
        if verbose:
            print(f"Updated status/timestamps for {updated_flights_count} existing flights.")

    # Append only new telemetry positions
    if not new_positions.empty:
        new_positions.to_sql('dim_flight_position', engine, if_exists='append', index=False)
        if verbose:
            print(f"Appended {len(new_positions)} new telemetry points.")

    return inserted_flights_count, added_telemetry_count


# =========================================================================
def enrich_dim_airlines(existing_airlines, raw_flights_df, verbose=False):
    """
    Updates dim_airline with missing IATA codes and country flags discovered in the live telemetry stream,
    and appends any brand-new airlines that weren't in the reference database.

    Args:
        existing_airlines (pd.DataFrame): Current dim_airline DataFrame loaded from the database.
        raw_flights_df (pd.DataFrame): Raw flight telemetry DataFrame containing live airline attributes.
        verbose (bool): If True, prints counts of updated and newly added airlines.

    Returns:
        pd.DataFrame: Updated and enriched dim_airline DataFrame.
    """
    # Extract airline info from the raw flights payload
    # We use raw_flights_df because 'flag' and 'airline_iata' were dropped during clean_flights
    cols = ['airline_icao', 'airline_iata', 'flag']
    live_airlines = raw_flights_df[[c for c in cols if c in raw_flights_df.columns]].dropna(subset=['airline_icao'])

    # Deduplicate so we only have one row per airline
    live_airlines = live_airlines.drop_duplicates(subset=['airline_icao'])

    # Convert to dictionary for fast mapping
    iata_mapping = dict(zip(live_airlines['airline_icao'], live_airlines.get('airline_iata', pd.Series())))
    flag_mapping = dict(zip(live_airlines['airline_icao'], live_airlines.get('flag', pd.Series())))

    # Patch the existing dimensions
    # If iata_code is null or a placeholder like '000', overwrite it with live data
    needs_iata = existing_airlines['iata_code'].isnull() | (existing_airlines['iata_code'] == '000')
    patched_iata_count = (needs_iata & existing_airlines['icao_code'].map(iata_mapping).notnull()).sum()
    existing_airlines.loc[needs_iata, 'iata_code'] = existing_airlines.loc[needs_iata, 'icao_code'].map(
        iata_mapping).fillna(existing_airlines['iata_code'])

    # If country_code (flag) is missing, overwrite it
    needs_flag = existing_airlines['country_code'].isnull()
    patched_flag_count = (needs_flag & existing_airlines['icao_code'].map(flag_mapping).notnull()).sum()
    existing_airlines.loc[needs_flag, 'country_code'] = existing_airlines.loc[needs_flag, 'icao_code'].map(
        flag_mapping).fillna(existing_airlines['country_code'])

    # ================================================
    # Append new airlines missing from the database
    existing_icaos = set(existing_airlines['icao_code'].dropna())
    new_airlines = live_airlines[~live_airlines['airline_icao'].isin(existing_icaos)].copy()
    added_airlines_count = len(new_airlines)

    # If there are new airlines, format them and append
    if not new_airlines.empty:
        new_airlines = new_airlines.rename(columns={
            'airline_icao': 'icao_code',
            'airline_iata': 'iata_code',
            'flag': 'country_code'
        })
        new_airlines['airline_name'] = 'UNKNOWN_AIRLINE'

        # Align columns to match the existing DataFrame
        cols_to_keep = ['icao_code', 'iata_code', 'airline_name', 'country_code']
        new_airlines = new_airlines[[c for c in cols_to_keep if c in new_airlines.columns]]

        # Merge historical dim_airlines and new rows
        existing_airlines = pd.concat([existing_airlines, new_airlines], ignore_index=True)

    if verbose:
        print(f"Enriched {patched_iata_count} airline IATA codes and {patched_flag_count} country flags.")
        print(f"Appended {added_airlines_count} brand-new airlines from live stream.")

    return existing_airlines


# =========================================================================
def enrich_dim_aircraft(dim_aircraft, df_live_aircraft_patch, verbose=False):
    """
    Enriches dim_aircraft by identifying new aircraft from live telemetry and
    using historical fleet data to fill missing registration numbers.

    Args:
        dim_aircraft (pd.DataFrame): Current dim_aircraft DataFrame loaded from the database.
        df_live_aircraft_patch (pd.DataFrame): Live aircraft metadata patch from telemetry.
        verbose (bool): If True, prints counts of newly added aircraft and registration enrichments.

    Returns:
        pd.DataFrame: Enriched and deduplicated dim_aircraft DataFrame.
    """
    if df_live_aircraft_patch.empty:
        if verbose:
            print("Live aircraft patch was empty. No aircraft enriched.")
        return dim_aircraft.copy()

    # Standardize the patch column name for the merge
    df_master = df_live_aircraft_patch.rename(columns={'aircraft_hex': 'hex'}).copy()

    # Extract reference keys from the existing dimension to create a lookup
    fleet_lookup = dim_aircraft[['hex', 'reg_number']].rename(columns={'reg_number': 'reg_from_fleet'})

    # Merge df_master with fleet_lookup on 'hex' using a left-join
    df_master = df_master.merge(fleet_lookup, on='hex', how='left')

    # Count how many missing reg numbers we are about to fill from fleet lookup
    missing_reg_mask = df_master['reg_number'].isnull() | (df_master['reg_number'] == 'UNKNOWN_REG')
    has_fleet_reg = df_master['reg_from_fleet'].notnull() & (df_master['reg_from_fleet'] != 'UNKNOWN_REG')
    enriched_regs_count = (missing_reg_mask & has_fleet_reg).sum()

    # Fill missing 'reg_number' in df_master with 'reg_from_fleet'
    df_master['reg_number'] = df_master['reg_number'].fillna(df_master['reg_from_fleet'])

    # Drop the temporary 'reg_from_fleet' column
    df_master = df_master.drop(columns=['reg_from_fleet'])

    # Fill any remaining unmapped Null values in 'reg_number' with 'UNKNOWN_REG'
    df_master['reg_number'] = df_master['reg_number'].fillna('UNKNOWN_REG')

    # Identify completely new aircraft missing from dim_aircraft
    existing_hexes = set(dim_aircraft['hex'].dropna())
    new_rows = df_master[~df_master['hex'].isin(existing_hexes)].copy()
    added_aircraft_count = len(new_rows)

    # Combine the historical dim_aircraft with the new rows
    if not new_rows.empty:
        # Rename to match the database schema
        if 'aircraft_icao' in new_rows.columns:
            new_rows = new_rows.rename(columns={'aircraft_icao': 'icao_code'})

        # Ensure fallback values for missing schema columns
        if 'iata_code' not in new_rows.columns:
            new_rows['iata_code'] = '000'
        if 'airline_icao' not in new_rows.columns:
            new_rows['airline_icao'] = '000'

        # Select only valid schema columns to prevent SQLAlchemy crashes
        valid_schema_cols = ['hex', 'reg_number', 'icao_code', 'iata_code', 'model', 'manufacturer', 'airline_icao']

        # Guarantee airline_icao is carried over
        if 'airline_icao' not in new_rows.columns:
            new_rows['airline_icao'] = '000'

        new_rows = new_rows[[c for c in valid_schema_cols if c in new_rows.columns]]

        enriched_dim = pd.concat([dim_aircraft, new_rows], ignore_index=True)
    else:
        enriched_dim = dim_aircraft.copy()

    # Clean up duplicates based on hex
    enriched_dim = enriched_dim.drop_duplicates(subset=['hex']).reset_index(drop=True)

    if verbose:
        print(f"Enriched {enriched_regs_count} aircraft registration numbers from reference fleet.")
        print(f"Appended {added_aircraft_count} brand-new aircraft from live stream.")

    return enriched_dim


def enrich_dim_airports(existing_airports, raw_flights_df, verbose=False):
    """
    Patches missing IATA codes in dim_airport using live flight telemetry.

    Args:
        existing_airports (pd.DataFrame): Current dim_airport DataFrame loaded from the database.
        raw_flights_df (pd.DataFrame): Raw flight telemetry DataFrame containing airport mappings.
        verbose (bool): If True, prints the count of successfully enriched airport IATA codes.

    Returns:
        pd.DataFrame: Enriched dim_airport DataFrame.
    """
    # Check if departure/arrival IATA mapping data exists in the live flight stream
    dep_cols = [c for c in ['dep_icao', 'dep_iata'] if c in raw_flights_df.columns]
    arr_cols = [c for c in ['arr_icao', 'arr_iata'] if c in raw_flights_df.columns]

    mappings = {}

    if len(dep_cols) == 2:
        dep_map = raw_flights_df[['dep_icao', 'dep_iata']].dropna().drop_duplicates()
        mappings.update(dict(zip(dep_map['dep_icao'], dep_map['dep_iata'])))

    if len(arr_cols) == 2:
        arr_map = raw_flights_df[['arr_icao', 'arr_iata']].dropna().drop_duplicates()
        mappings.update(dict(zip(arr_map['arr_icao'], arr_map['arr_iata'])))

    enriched_airports_count = 0

    if mappings:
        # If IATA_code is null or '000', overwrite it with discovered live data
        needs_iata = existing_airports['iata_code'].isnull() | (existing_airports['iata_code'] == '000')

        # Calculate how many will actually change before applying the map
        mapped_values = existing_airports.loc[needs_iata, 'icao_code'].map(mappings)
        enriched_airports_count = (needs_iata & mapped_values.notnull()).sum()

        existing_airports.loc[needs_iata, 'iata_code'] = (
            mapped_values.fillna(existing_airports['iata_code'])
        )

    if verbose:
        print(f"Enriched {enriched_airports_count} airport IATA codes from live telemetry.")

    return existing_airports

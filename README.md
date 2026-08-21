# DST Airlines Data Pipeline
An automated ETL and data processing pipeline designed to ingest, clean and structure aviation datasets into a clean star schema relational database format using the AirLabs API.

## Project Context
*This repository originally began as a collaborative group project. I have since taken full ownership of this fork to independently expand the architecture, optimize the data pipeline, and build out the frontend visualization components.*

* **Pipeline Architect & Core Developer:** Leoni Gilke
  * **Independent Additions:** Interactive flight mapping, Plotly UI/UX design, CDN size optimization, and dynamic route categorization.
  * **Core Architecture:** Designed, implemented, and authored the main ETL codebase (`pipeline_init.py`, `pipeline_monthly.py`, `pipeline_daily.py`), utilities (`pipeline_utils.py`), API wrappers (`api_utils.py`), and configuration frameworks.
* **Original Project Team:** Rustam U.
  * Collaborated on initial project conceptualization, analytical reporting, and downstream dashboard development.
---

## Live Interactive Dashboard
As part of the independent expansion of this project, a high-performance interactive flight tracking map was built using Python and Plotly. 

![Flight Map Preview](docs/map_preview.png)

**Key Features of the Map:**
* **Dynamic Route Categorization:** Automatically flags live telemetry data as Inbound or Outbound based on configured target hubs (EGLL, LFPG, LTFM).
* **High-Contrast UI:** Utilizes neon complementary color pairs against a `carto-darkmatter` base map for maximum accessibility and readability.
* **Performance Optimized:** Data is aggressively pre-filtered before rendering, and Plotly.js is loaded via CDN, reducing the final HTML export size from ~6MB to under 150KB for instantaneous browser loading.
* **Polished Tooltips:** Uses custom HTML templates to clean raw ISO timestamps and replace null values with clean UI elements.

---

## Project Goal
An educational data engineering initiative to build an automated ingestion pipeline for real-time airline operations data using the AirLabs API, transforming raw telemetry into an optimized relational Star Schema.

---

## Evaluation of Data Sources
Our team evaluated several flight data providers—including **OpenSky** and **Aviationstack**—before selecting **AirLabs** for our data pipeline based on three key factors:
* **Data Suitability:** AirLabs provides the specific granularity required, including flight numbers, real-time status updates, and aircraft type details.
* **Budget-Friendly Constraints:** The free-tier allowance of 1,000 requests per month is ideal for our academic development lifecycle.
* **Ease of Implementation:** Highly accessible documentation allowing fast authentication and data extraction.

---

## Data-Driven Modeling Methodology
To ensure optimal storage efficiency and data integrity, data types and column constraints are aligned with the operational requirements of our downstream database schema, ensuring the pipeline handles real-world variability cleanly.

---

## Workflow Pipeline Architecture
Our pipeline follows a structured architecture divided across distinct operational scripts for optimal modularity:

1. **Extraction (`api_utils.py`):** Handles communication protocols, session handlers, and endpoint requests with built-in API quota protection and raw CSV caching.
2. **Transformation (`pipeline_utils.py`):** Cleans data, standardizes naming conventions, backfills missing attributes, and structures information into Fact and Dimension tables.
3. **Execution & Loading (`etl_pipeline/`):** Orchestrates database loading via a **3-script approach** separating initialization, monthly reference syncs, and daily incremental telemetry runs.


---

## Setup & Configuration
1. Clone the repository to your local machine.
2. Obtain an API key from [AirLabs](https://airlabs.co).
3. Create a `.env` file in the project root directory and add your key:
   ```text
   AIRLABS_API_KEY=your_key_here
   ```
4. Install the required dependencies:
   ```Bash
   pip install pandas SQLAlchemy python-dotenv requests
   ```
5. Execute the Pipeline: Navigate to the project root directory and run the 3 scripts:
    ```Bash
    python etl_pipeline/pipeline_init.py
    python etl_pipeline/pipeline_monthly.py
    python etl_pipeline/pipeline_daily.py
    ```
   
---

## Data Sample
The following JSON structure demonstrates the data captured from the `flights` endpoint:
```json
{
    "hex": "347645",
    "reg_number": "EC-OEA",
    "flag": "ES",
    "lat": 34.810714,
    "lng": -4.78554,
    "alt": 11602,
    "dir": 51,
    "speed": 871,
    "v_speed": 0,
    "flight_number": "5772",
    "flight_icao": "IBB5772",
    "flight_iata": "NT5772",
    "dep_icao": "GCLP",
    "dep_iata": "LPA",
    "arr_icao": "LEAM",
    "arr_iata": "LEI",
    "airline_icao": "IBB",
    "airline_iata": "NT",
    "aircraft_icao": "E295",
    "updated": 1783179416,
    "status": "en-route",
    "type": "adsb"
}
```

---

## Data Pipeline Utilities
The `pipeline_utils.py` module contains core transformation, cleaning, and incremental loading logic:

* **`clean_airlines_db(df)`**: Processes raw airline data, filters for valid ICAO primary keys, standardizes missing IATA codes with `'000'`, maps API `'flag'` attributes to `'country_code'` to satisfy foreign key constraints with `dim_country`, converts missing values to proper SQL nulls, and handles deduplication.
* **`clean_airports_db(df)`**: Cleans airport records by ensuring mandatory coordinate data and ICAO primary keys exist, while normalizing missing IATA codes.
* **`clean_aircraft_db(df)`**: Formats fleet metadata for `dim_aircraft`, dropping unidentifiable records lacking a hex code and safely backfilling missing registrations with `'UNKNOWN_REG'`.
* **`clean_cities_db(df)` & `clean_countries_db(df)`**: Standardize geographical references, enforce uppercase formatting for country codes, and eliminate duplicates.
* **`clean_schedules(df)`**: Standardizes raw airport schedule datasets, converts UNIX/string times to standard datetimes, and renames delay metrics for schema alignment.
* **`clean_flights(df_flights)`**: 
  * Parses raw real-time flight telemetry, dropping noisy columns and safely generating a `time_key` from UNIX timestamps.
  * Generates composite smart keys (`position_key` and `flight_id`) with strict `.drop_duplicates(subset=['position_key'])` deduplication to prevent SQLite `UNIQUE constraint failed` errors.
  * Extracts a live aircraft metadata patch (`df_live_aircraft_patch`) for downstream dimension enrichment.
* **`build_fact_flight(fact_flights, df_clean_schedules)`**: Left-joins cleaned schedules onto real-time live flights to construct the fully realized fact table matching the target schema.
* **`load_incremental_flights(engine, fact_flights, dim_flight_position)`**: Queries the database to prevent duplicate ingestion of existing records, appends new deltas safely, and logs audit metrics.
* **`enrich_dim_aircraft`, `enrich_dim_airlines`, & `enrich_dim_airports`**: Incrementally update dimensions using live telemetry data feeds, dynamically patching missing metadata and safely appending brand-new entities.

### Verbose Logging Control (`verbose`)
All pipeline scripts and cleaning functions support an optional boolean `verbose` flag (default: `False`). When enabled (`verbose=True`), the pipeline outputs detailed processing statistics, record counts at each transformation phase, and incremental merge metrics directly to the terminal for debugging and audit transparency.

---

## Pipeline Architecture & Execution
The `pipeline_utils.py` module contains core transformation, cleaning, and incremental loading logic:
>*outdated*

---

## The 3-Script Execution Approach
To maintain clean separation of concerns between fast-changing operational telemetry and slow-changing global reference metadata, the pipeline is structured into three discrete scripts:

1. **Database Initialization (`pipeline_init.py`)**
   * **Purpose:** Sets up the database schema from `database_schema/schema.sql`, generates the 10-year calendar (`dim_date`) and minute-grain time dimension (`dim_time`), and executes the initial baseline ingest.
   * **Execution:** Run manually once.

2. **Monthly Static Data Refresh (`pipeline_monthly.py`)**
   * **Purpose:** Periodically synchronizes the warehouse’s dimension tables with the latest global aviation reference data (airports, airlines, cities, countries, and aircraft fleets).
   * **Execution Strategy:** Employs a full-refresh pattern for reference entities. It clears stale static records safely via `DELETE` statements and re-inserts fresh, cleaned payloads from the AirLabs API.
   * **Safety Safeguards:** Implements intelligent merge safeguards that inspect existing database records to preserve and protect established daily patches (such as incrementally enriched IATA codes, country codes, and aircraft registration numbers like `UNKNOWN_REG`) from being overwritten by null or default API values.

3. **Daily Incremental Ingestion (`pipeline_daily.py`)**
   * **Purpose:** Pulls live flight telemetry and schedules, cleans and structures them into `fact_flight` and `dim_flight_position`, live-patches missing dimension metadata, and appends new unseen flights incrementally.
   * **Execution Strategy:** Runs routinely to capture live delta states and append telemetry points safely.

---

## Automated Execution (Cron Jobs)
For production or scheduled server environments, the monthly and daily scripts can be automated using Cron:
```Bash
# 1. Monthly Refresh: Runs at 02:00 AM on the 1st day of every month
0 2 1 * * /usr/bin/python3 /path/to/project/etl_pipeline/pipeline_monthly.py >> /path/to/project/logs/monthly.log 2>&1

# 2. Daily Flight Ingestion: Runs every day at 05:00 AM
0 5 * * * /usr/bin/python3 /path/to/project/etl_pipeline/pipeline_daily.py >> /path/to/project/logs/daily.log 2>&1
```
---

## Pipeline & Data Model Improvements

* **Composite Key Merging for Flight Schedules:** Updated the `build_fact_flight` pipeline utility to perform a composite join (`flight_icao` + calendar date key) when attaching schedule telemetry to live flights. This eliminates cross-day data corruption, prevents schedule timestamp nullification, and guarantees that inbound and outbound flight records align accurately with their correct operational dates.
* **Idempotent Telemetry Ingestion:** Enhanced `load_incremental_flights` to query existing `position_key` records prior to insertion. This prevents unique constraint failures when executing the daily pipeline multiple times within the same minute, ensuring safe and repeatable upserts.
* **Automated Stale Data Cleanup:** Integrated a pre-execution pipeline step in `pipeline_daily.py` utilizing a database-relative date threshold (`MAX(updated_date_key)`) to automatically transition stale "en-route" flights older than 24 hours to "assumed-landed", preventing inflated active flight metrics caused by incomplete global telemetry.
* **Stable Flight Identity Architecture (`flight_id`):** Refactored `flight_id` generation from callsign + poll date to callsign + scheduled/flight date. This guarantees that the same flight maintains a stable identifier throughout its operating day, allowing subsequent pipeline runs to update its status rather than duplicating rows, while correctly generating fresh IDs for future recurring flights.
* **High-Precision Telemetry Tracking (`position_key`):** Upgraded `position_key` generation to include high-precision seconds (`HHMMSS` via `telemetry_time_str`), preventing rapid multi-poll telemetry overwriting or data loss within the same minute.
* **Smart Incremental State Upserts (`load_incremental_flights`):** Refactored the loader to split incoming payloads into `new_facts` and `existing_facts`. Implemented an explicit SQL `UPDATE` loop for existing active flight records to refresh live statuses, coordinates, and timestamps seamlessly throughout the day without ghost accumulation.

---

## Future Enhancement
* **Directional Movement Tracking (movement_type)**: While current analytical queries successfully determine flight directionality using origin and destination code matching relative to the primary hub (LHR), introducing an explicit boolean or categorical movement_type attribute in a future iteration would streamline real-time operational auditing. This would allow the ingestion layer to instantly flag turnaround times and gate-congestions metrics without secondary relational filtering."

---
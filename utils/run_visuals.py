import sys
from pathlib import Path

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
from sqlalchemy import create_engine
from utils.data_analysis import AirlineVisualizer

# Connect to database
DB_PATH = PROJECT_ROOT / 'database' / 'airlines_warehouse.db'
engine = create_engine(f'sqlite:///{DB_PATH.as_posix()}')

# Query scheduled hub traffice (EGLL, LTFM, LFPG)
query = """
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

df = pd.read_sql(query, engine)

# Instantiate visualizer and render plot
viz = AirlineVisualizer(output_dir='outputs')
viz.plot_top_hub_airlines(df, top_n=5)
print("Successfully saved top_hub_airlines.png to /outputs!")
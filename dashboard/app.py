import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
st.set_page_config(
    page_title="Airlines | Live Operations Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# DATABASE CONNECTION
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "airlines_warehouse.db"

@st.cache_resource
def get_db_engine():
    """Create and cache read-only connection to SQLite warehouse."""
    return create_engine(f"sqlite:///{DB_PATH.as_posix()}")

engine = get_db_engine()

# -----------------------------------------------------------------------------
# HELPER QUERY FUNCTIONS
@st.cache_data(ttl=300)         # 300s -> Refresh every 5 Min
def get_distinct_active_airlines_count() -> int:
    """Queries warehouse to count unique active airline ICAOs from fact_flight."""
    if not DB_PATH.exists():
        return 0

    query = text("""
        SELECT COUNT(DISTINCT airline_icao)
        FROM fact_flight
        WHERE airline_icao IS NOT NULL AND airline_icao != 'UNKNOWN';
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query).scalar()
            return int(result) if result else 0
    except Exception as e:
        st.error(f"Error quering active airlines: {e}")

# Fetch dynamic count
active_carrier_count = get_distinct_active_airlines_count()

# -----------------------------------------------------------------------------
# SIDEBAR FILTERS
st.sidebar.title("✈️ Filter Operations")

# Base Example
selected_hub = st.sidebar.selectbox(
    "Select Target Hub",
    options = ["All Hubs", "EGLL", "LTFM", "LFPG"],
    index = 0
)

st.sidebar.markdown("---")
st.sidebar.caption("Data Source: SQLite Warehouse ('airlines_warehouse.db')")

# -----------------------------------------------------------------------------
# MAIN DASHBOARD
st.title("🛫 Airline Operations & Fleet Intelligence")
st.markdown("Real-time telemetry, market share analysis, and fleet quality metrics.")

# Top-level KPI Metrics Row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label = "Tracked Airports", value = "3")
with col2:
    st.metric(
        label = "Active Airlines",
        value = f"{active_carrier_count}"
    )
with col3:
    st.metric(label = "Database Status", value = "Connected" if DB_PATH.exists() else "Offline"
    )
with col4:
    st.metric(label = "Release", value = "v1.2.0")

st.divider()

st.info("Test")
## [Unreleased]
### Added
- **Standalone Visual Runner (`utils/run_visuals.py`):** Created an automated execution script that queries the SQLite warehouse (`airlines_warehouse.db`), extracts data freshness timestamps, executes all `AirlineVisualizer` reports, and exports versioned artifacts to `/outputs`.
- **Data Engineering Visualization Suite (`utils/data_analysis.py`):** Implemented the `AirlineVisualizer` class, providing reusable, standardized Matplotlib plotting methods for warehouse reporting:
  - `plot_fleet_coverage_audit()`: 2-panel audit visual tracking enriched vs. `UNKNOWN_MODEL` fleet ratios alongside top airframe type distributions.
  - `plot_registration_coverage()`: Dual donut and bar chart auditing mapped vs. `UNKNOWN_REG` tail numbers.
  - `plot_top_airlines()`: Volume ranking of top active carriers across operational telemetry feeds.
  - `plot_top_hub_airlines()`: Side-by-side horizontal bar charts comparing carrier market share (%) across target hubs (`EGLL`, `LTFM`, `LFPG`).
  - `plot_hub_market_share_donuts()`: Multi-donut visualization displaying airline market share concentration at target hub airports.
  - `plot_hub_consolidation_comparison()`: Stacked horizontal bar chart measuring Home Flag Carrier market share vs. foreign competition across target hubs.
  - `plot_flight_altitude_distribution()`: Telemetry histogram overlaying Kernel Density Estimation (KDE) and operational median altitude reference lines.
- **Paginated Fleet Ingestion:** Implemented `ingest_aircraft_paginated()` in `pipeline_utils.py` to systematically fetch 50-record API offset pages from the AirLabs `/fleets` endpoint.

### Fixed
- **Axis & Gridline Styling:** Streamlined plot aesthetics across dual-panel figures by selectively removing vertical grid lines on vertical bar charts and setting horizontal spacing to eliminate y-axis label clipping.

### Changed
- **Documentation Alignment:** Updated `README.md` with standardized visual specification blocks and copied audit artifacts into `docs/figures/`.
- **Non-Destructive Fleet Refactor:** Updated `pipeline_monthly.py` Safeguard 3 to merge reference updates into SQLite safely without issuing destructive `DELETE` statements on live-streamed hex codes.
- **Aircraft Cleaning Fallback:** Enhanced `clean_aircraft_db()` to fall back to `icao_code` whenever raw API payloads omit human-readable `model` names.

---

## [1.1.0] - 2026-08-21
### Added
- Expanded the daily ETL pipeline to ingest flight schedules for 3 distinct airports (Added 'LTFM' (Istanbul Airport) and 'LFPG' (Charles de Gaulle Airport) to 'EGLL' (Heathrow Airport)).
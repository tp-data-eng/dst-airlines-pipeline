## [Unreleased]
### Added
- **Data Quality Reporting Suite (`AirlineVisualizer`):** Added automated visual reporting capabilities exported directly to `/outputs`:
  - `plot_fleet_coverage_audit()`: Two-panel audit tracking enriched vs. `UNKNOWN_MODEL` fleet ratios and top resolved commercial airframes.
  - `plot_registration_coverage()`: Dual donut and bar chart auditing mapped vs. `UNKNOWN_REG` tail numbers.
  - `plot_top_aircraft_models()`: Horizontal bar chart of frequent fleet models with custom highlight colors for unmapped entities.
  - `plot_top_airlines()`: Volume ranking of top active carriers across operational telemetry feeds.
  - `plot_flight_altitude_distribution()`: Telemetry histogram for altitude verification and outlier spot-checking.
- **Paginated Fleet Ingestion:** Implemented `ingest_aircraft_paginated()` in `pipeline_utils.py` to systematically fetch 50-record API offset pages from the AirLabs `/fleets` endpoint.

### Changed
- **Non-Destructive Fleet Refactor:** Updated `pipeline_monthly.py` Safeguard 3 to merge reference updates into SQLite safely without issuing destructive `DELETE` statements on live-streamed hex codes.
- **Aircraft Cleaning Fallback:** Enhanced `clean_aircraft_db()` to fall back to `icao_code` whenever raw API payloads omit human-readable `model` names.
---

## [1.1.0] - 2026-08-21
### Added
- Expanded the daily ETL pipeline to ingest flight schedules for 3 distinct airports (Added 'LTFM' (Istanbul Airport) and 'LFPG' (Charles de Gaulle Airport) to 'EGLL' (Heathrow Airport)).
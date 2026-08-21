# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]
### Added
- Interactive flight map visualizing live aircraft coordinates using Plotly `scatter_mapbox`.
- Dynamic route categorization (Inbound/Outbound/Other) for target airports.
- Custom HTML hover tooltips with formatted, human-readable timestamps.
- High-contrast neon color palette for distinct route visibility.

### Changed
- Optimized map generation by filtering globally down to TARGET_AIRPORTS before rendering.
- Reduced Plotly export file size from ~6MB to <150KB by enabling CDN integration.

---

## [1.1.0] - 2026-08-21
### Added
- Expanded the daily ETL pipeline to ingest flight schedules for 3 distinct airports. Added 'LTFM' (Istanbul Airport) and 'LFPG' (Charles de Gaulle Airport) to the existing 'EGLL' (Heathrow Airport) configuration.

---

## [1.0.0] - The Group Baseline
### What it represents
The exact state of the pipeline at the end of the collaborative group project. This includes:
- AirLabs API extraction specifically configured for London Heathrow Airport.
- 3NF SQLite database architecture.
- Initial data cleaning utilities and extraction scripts.
- Baseline Power BI dashboard setup.
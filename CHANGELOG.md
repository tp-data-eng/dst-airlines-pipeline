## [1.1.0] - 2026-08-21
### Added
- Expanded the daily ETL pipeline to ingest flight schedules for 3 distinct airports (Added 'LTFM' (Istanbul Airport) and 'LFPG' (Charles de Gaulle Airport) to 'EGLL' (Heathrow Airport)).

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
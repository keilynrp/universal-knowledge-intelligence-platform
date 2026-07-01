"""OpenAlex analytical lake.

A controlled, filtered ingestion of OpenAlex (CC0) into a persistent DuckDB
star schema for historical + cross-source scientometric analysis.

Design goals:
- Start with a *targeted subset* (a journal ISSN-L list × a year window) pulled
  via the OpenAlex API, so no 300 GB snapshot download is required.
- Scale to the *full snapshot* later by widening LakeScope and swapping the
  works source to the S3 snapshot — the transform + schema stay identical.
- Support automated incremental refresh via `from_updated_date` watermarking.

Modules:
- config:    LakeScope (what to ingest) + defaults.
- schema:    DuckDB DDL for the star schema.
- transform: pure OpenAlex-work JSON -> normalized rows (unit-tested core).
- store:     DuckDB persistence (create schema, upsert rows, watermark).
"""

# FZJ Knowledge Graph Pipeline

> A data pipeline harvesting GitHub repositories, resolving contributor
> ORCIDs, retrieving associated publications via DataCite, and storing
> the result as a FAIR-aligned RDF knowledge graph.

## Overview

The pipeline harvests the IAS-9 GitHub organisation
(`github.com/Materials-Data-Science-and-Informatics`), resolves contributor
identities via the ORCID Public API, retrieves their linked publications from
DataCite, and assembles all data into an RDF graph using schema.org + PROV-O.
The graph is serialised to Turtle and JSON-LD, and rendered as an interactive
HTML visualisation using pyvis.

## Prerequisites

- Python 3.11+
- A GitHub personal access token (`public_repo` scope is sufficient)

## Quick Start (Local)

```bash
# 1. Clone or unzip the project
cd fzj-kg-pipeline

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your GitHub token
cp .env.example .env
# Edit .env and set: GITHUB_TOKEN=ghp_your_token_here

# 4. Run the pipeline (10 repos by default)
python pipeline.py --max-repos 10

# 5. Open the interactive graph in your browser
open output/graph.html       # macOS
xdg-open output/graph.html   # Linux
```

**Full run** (all 37 IAS-9 repositories):
```bash
python pipeline.py --max-repos 37
```

**Verbose output**:
```bash
python pipeline.py --max-repos 10 --log-level DEBUG
```

## Quick Start (Docker)

```bash
# 1. Configure your GitHub token
cp .env.example .env
# Edit .env and set GITHUB_TOKEN

# 2. Build and run
docker-compose up

# 3. Open the output
open output/graph.html
```

**Rebuild after code changes:**
```bash
docker-compose up --build
```

## Running Tests

Tests are fully offline — all API calls are mocked. No `.env` file required.

```bash
# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_graph_builder.py -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=term-missing
```

---

## Design Decisions

### Vocabulary: schema.org

This pipeline uses `schema.org` as its primary vocabulary, deliberately
mirroring the Helmholtz Knowledge Graph's own data model. The HKG uses
`schema:Person`, `schema:SoftwareSourceCode`, `schema:ScholarlyArticle`, and
`schema:Dataset` for the same entity types this pipeline produces.

The `https://schema.org/` namespace (HTTPS) is used throughout — the old
`http://schema.org/` form is deprecated in current Linked Data practice.

The DataCite `resourceTypeGeneral` → schema.org type mapping follows the
official **DataCite Metadata Schema 4.4 to Schema.org Mapping** crosswalk:
https://doi.org/10.5281/zenodo.7661399

### Identifier Strategy: Real IRIs as node subjects

ORCID iDs and DOIs are used as RDF node subjects (the `@id` in JSON-LD),
following Linked Data best practices:

| Entity | Node IRI |
|--------|----------|
| Person (ORCID resolved) | `https://orcid.org/0000-0002-XXXX-XXXX` |
| Person (no ORCID) | `urn:hkg:person:{md5(name)}` — hash-based local IRI |
| GitHub repository | `https://github.com/org/repo` (the HTML URL) |
| Publication | `https://doi.org/10.XXXX/...` |

The hash-based local IRI for contributors without ORCIDs mirrors the HKG's
own fallback strategy for entities without external persistent identifiers.

### Provenance: `prov:wasDerivedFrom`

Every entity node carries a `prov:wasDerivedFrom` triple linking to the API
endpoint from which the data was harvested:

- Repositories → `https://api.github.com/repos/{org}/{repo}`
- ORCID persons → `https://pub.orcid.org/v3.0/{orcid-path}`
- Publications → `https://api.datacite.org/dois/{doi-encoded}`

This is consistent with the HKG's provenance architecture, where every
graph entity links back to its raw source record via `prov:has_provenance`.

### API Choice: DataCite REST over GraphQL

The DataCite REST API (`/dois` endpoint) is used as the primary approach.
It is simpler, well-documented, and sufficient for this task scope.

### Visualisation:  pyvis

pyvis generates a **standalone interactive HTML file** using the vis.js
network library. Unlike a matplotlib static PNG, the output can be:
- Opened directly in any browser without a running server
- Screenshared during the interview with interactive hover/zoom
- Saved as a single self-contained file for distribution

Provenance edges (`prov:wasDerivedFrom`) are excluded from the visualisation
to keep the graph readable. They are present in the Turtle and JSON-LD output.

---

## Output Files

| File | Description |
|------|-------------|
| `output/graph.ttl` | Full RDF graph — Turtle serialisation |
| `output/graph.jsonld` | Full RDF graph — JSON-LD serialisation |
| `output/graph.html` | Interactive pyvis visualisation |

---

## Known Limitations

- **ORCID matching is name-based (first result only).** GitHub display names
  are not always the researcher's legal name as registered in ORCID. Contributors
  without a resolved ORCID still appear in the graph with a hash-based IRI
  and are linked to their repositories.

- **DataCite coverage is ORCID-dependent.** Publications are retrieved by
  querying DataCite for works whose creator nameIdentifiers include the ORCID.
  If a researcher has not registered their ORCID in their DataCite records,
  their publications will not appear.

- **GitHub contributor list reflects commit activity only.** Team members who
  contribute through issues, reviews, or project management without committing
  code will not appear in the contributors endpoint.

---

## What a Production Version Would Add

- **Pydantic validation models** for type-safe validation of each record
  before graph insertion — mirroring the HKG's own processing layer.
- **Apache Airflow orchestration** for scheduled weekly runs with retry logic,
  task isolation, and monitoring dashboards.
- **PostgreSQL persistence** of the raw API responses, enabling re-mapping
  when the data model evolves without re-harvesting all sources.
- **Incremental harvesting** using GitHub's `since` parameter (commits) and
  DataCite's `updated` date filter to reduce weekly pipeline execution time.
- **SSSOM mapping files** to document the DataCite → schema.org field mappings
  as machine-readable, shareable artefacts — as planned in the HKG roadmap.
- **Graph quality monitoring** via SPARQL-based consistency probes run
  post-assembly to detect structural anomalies and entity duplication.

---

## Project Structure

```
fzj-kg-pipeline/
├── pipeline.py        # CLI entry point — orchestrates all five stages
├── harvester.py       # GitHub REST API client (repos + contributors)
├── resolver.py        # ORCID Public API lookup (name → ORCID iD)
├── publications.py    # DataCite REST API client (ORCID → publications)
├── graph_builder.py   # rdflib graph construction (schema.org + PROV-O)
├── visualise.py       # pyvis interactive HTML visualisation
├── tests/             # pytest suite — all HTTP calls mocked
├── requirements.txt   # Pinned dependencies
├── .env.example       # Template for GITHUB_TOKEN configuration
├── Dockerfile         # Single-command Docker execution
├── docker-compose.yml # Docker Compose configuration
└── output/            # Pipeline output directory (created at runtime)
```

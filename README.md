# AVELTURA — Vel Engine Analysis Platform

> Mathematical optimization engine for automotive data. Drop in a car, get a full modification plan backed by physics, statistics, and verified spec data. Runs entirely on local hardware.

---

## Table of Contents

- [What is this](#what-is-this)
- [Hardware](#hardware)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Data Pipeline](#data-pipeline)
- [API Reference](#api-reference)
- [Optimization Engine](#optimization-engine)
- [Services](#services)
- [File Reference](#file-reference)
- [Roadmap](#roadmap)
- [Changelog](#changelog)

---

## What is this

Aveltura is a homelab AI stack built around **Vel** — a RAG-powered engine analysis API that answers questions about cars, engines, and modifications using verified data it scrapes and indexes every night.

Started as a way to plan an SC300 build. Turned into a full engine analysis platform with:

- A vehicle-first data pipeline that scrapes Wikipedia by car generation and trim
- A hybrid BM25 + vector retrieval system that finds exact engine names and understands semantic queries
- A physics-based optimization engine that calculates mod plans using thermodynamics and fluid dynamics
- A Plotly Dash dashboard with live charts and a Vel query box
- An OpenAI-compatible API endpoint so it works with Open WebUI out of the box
- A nightly systemd pipeline that scrapes, cleans, normalizes, rebuilds, and reloads automatically

Everything runs on a single repurposed HP ZBook. No cloud. No subscription. No data leaves the machine.

---

## Hardware

| Component   | Spec                          |
|-------------|-------------------------------|
| CPU         | Intel i7-9850H (6c/12t)       |
| RAM         | 23.24 GB                      |
| GPU         | Quadro T2000 4GB              |
| Storage     | Samsung 990 Pro SSD           |
| OS          | CachyOS (Arch-based)          |
| Hostname    | TheAtHomeComp                 |
| Tailscale   | 100.104.58.38                 |

**Models running via Ollama:**
- `mistral` — LLM for RAG query responses
- `nomic-embed-text` — embeddings for vector retrieval

---

## Quick Start

### Prerequisites

```bash
# Python packages
pip install fastapi uvicorn llama-index llama-index-llms-ollama \
    llama-index-embeddings-ollama llama-index-retrievers-bm25 \
    plotly dash pandas numpy scipy requests beautifulsoup4 \
    python-dotenv slowapi textual --break-system-packages
```

### Environment

Create `/home/_homeos/engine-analysis/.env`:

```env
BASE_DIR=/home/_homeos/engine-analysis
MODEL_NAME=mistral
EMBED_MODEL=nomic-embed-text
REQUEST_TIMEOUT=600.0
VEL_API_KEY=your_key_here
VEL_PORT=8001
PERSIST_DIR=/home/_homeos/engine-analysis/storage
```

### Generate API key

```bash
python3 -c "import secrets; print('aveltura-vel-key-' + secrets.token_urlsafe(24))"
```

### Run the pipeline

```bash
cd /home/_homeos/engine-analysis
python manufacturer_discovery.py   # discover cars from manufacturer pages
python generation_scraper.py       # scrape each car by generation/trim
python car_cleaner.py              # clean, validate, merge duplicates
python scraper.py                  # scrape engine deep specs
python cleaner.py                  # clean engine specs
python normalizer.py               # normalize units, apply confidence scoring
python ingest_applications.py      # ingest vehicle applications
python rag.py --full               # build RAG index
python tableau_export.py           # generate BI export CSVs
python viz_engine.py               # generate Plotly charts
```

### Start services

```bash
sudo systemctl start vel.service
sudo systemctl start velframe-web.service
python dashboard.py  # port 8003
```

### Test

```bash
curl -s -X POST http://localhost:8001/query \
  -H "Authorization: Bearer $VEL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "What engine does the Toyota Supra MK4 use?"}' | python3 -m json.tool
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                         │
│  Open WebUI (8080)  │  Velframe (8002)  │  Dashboard (8003) │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                       VEL API (8001)                        │
│              FastAPI + LlamaIndex + Mistral 7B              │
│                                                             │
│  /query          — RAG query (Vel native)                   │
│  /v1/chat        — OpenAI-compatible endpoint               │
│  /optimize       — Physics optimization engine              │
│  /reload         — Hot-reload index                         │
│  /viz/*          — Chart generation                         │
│  /stats/*        — Statistical analysis                     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                      RAG ENGINE                             │
│                                                             │
│  BM25 Retriever ──┐                                        │
│                   ├─► QueryFusionRetriever (2:1 BM25)      │
│  Vector Retriever─┘         │                              │
│                             ▼                              │
│              nomic-embed-text embeddings                    │
│              Mistral 7B LLM response                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    DATA PIPELINE                            │
│                                                             │
│  manufacturer_discovery.py                                  │
│    └─► generation_scraper.py                               │
│          └─► car_cleaner.py                                │
│                └─► scraper.py (engine deep specs)          │
│                      └─► cleaner.py                        │
│                            └─► normalizer.py               │
│                                  ├─► engine_applications   │
│                                  └─► engine_normalized     │
└─────────────────────────────────────────────────────────────┘
```

### Document hierarchy

The RAG index contains three tiers of documents:

| Tier | Source | Example |
|------|--------|---------|
| Primary | `engine_applications.csv` | "Toyota Supra A80 uses 2JZ-GTE, 276hp, 1993-1998" |
| Secondary | `engine_normalized.csv` | "2JZ-GTE: 2998cc, 86x86mm, 8.5:1 compression" |
| Tertiary | `mods_specs.csv` | "Garrett G25-660: max 660hp, T3 flange" |

### Hybrid retrieval

BM25 handles exact keyword matches (`RB26DETT` → finds RB26DETT documents precisely). Vector retrieval handles semantic queries (`"twin turbo JDM inline-6 from the 90s"`). Both are fused with reciprocal rank fusion, BM25 weighted 2x.

```
Query: "What engine does the Supra MK4 use?"
  BM25:   finds docs containing "Supra" and "MK4" exactly
  Vector: finds semantically similar docs about Toyota sports cars
  Fusion: reranks combined results, BM25 matches rank higher
  Mistral: generates answer from top 6 docs, cites confidence level
```

---

## Data Pipeline

### Phase 1 — Manufacturer Discovery (`manufacturer_discovery.py`)

Reads 45 manufacturer seeds. Fetches each manufacturer's Wikipedia page. Extracts car model links using two strategies:

- **Section extraction** — finds "Models", "Vehicles", "Products" headers and pulls links
- **Navbox extraction** — finds manufacturer-specific navigation tables at page bottom

Filters using `looks_like_car_model()` — requires name to contain manufacturer name, look like a model code (M3, 911, GR86), or be a short alphanumeric (GTS, STI, WRX).

**Two-tier output:**
- Tier 1 (performance/sports/muscle/JDM) → `scrape_queue.csv` — scraped immediately
- Tier 2 (standard/truck/SUV) → `discovery_queue.txt` — scraped on future runs

### Phase 2 — Generation Scraper (`generation_scraper.py`)

For each car in `scrape_queue.csv`:

1. Searches Wikipedia for the car's main page
2. Detects generation-specific sub-pages using 8 patterns:
   - Ordinal words: "Fourth generation"
   - Chassis codes: `(E46)`, `(R34)`, `(A80)`
   - Platform codes: `(S550)`, `(F80)`, `(G80)`
   - Year ranges: `(1993–2002)`
3. Scrapes each generation's infobox for all engine/trim combinations
4. Splits multi-engine pages into separate rows

**Output:** `raw_vehicle_specs.csv` — one row per vehicle/generation/trim/engine

### Phase 3 — Car Cleaner (`car_cleaner.py`)

**Validation:**
- Filters non-car rows (formula cars, motorcycles, concepts)
- Marks implausible values as NULL (HP > 3000, displacement < 50cc, etc.)
- Cross-validates HP/displacement ratio (flags if > 0.5 HP/cc or < 0.02 HP/cc)

**Duplicate detection and smart merge:**

Groups by `vehicle + generation + trim`. For duplicate groups:

1. Collects all non-null values per field from all duplicate rows
2. Single value → keeps it
3. Multiple values → runs 4-factor confidence scoring:

| Factor | Points | Description |
|--------|--------|-------------|
| Plausibility range | 25 | Value within sane bounds for field type |
| HP/torque ratio | 25 | HP per litre between 20-500 |
| EPA corroboration | 25 | Displacement within ±150cc of EPA data |
| Seeds match | 25 | Within 15% of verified_seeds value |

Threshold: **70/100** to accept a merged field value.

**Output:** `clean_vehicle_specs.csv`

### Phase 4 — Normalizer (`normalizer.py`)

**Two streams:**

Stream A (vehicle-first): `clean_vehicle_specs.csv` → unit conversion → `engine_applications.csv`

Stream B (engine-first): `engine_specs.csv` → unit conversion + confidence scoring → `engine_normalized.csv`

**Unit conversions:**
- Power: kW × 1.341, PS × 0.9863, bhp = hp
- Torque: lb-ft × 1.356, kgm × 9.807
- Displacement: cu in × 16.387, litres × 1000
- Bore/stroke: inches × 25.4

**Confidence levels (highest wins):**

| Level | Source |
|-------|--------|
| `verified_manual` | `verified_seeds.csv` — hand-verified data |
| `epa_verified` | EPA displacement database cross-reference |
| `wikipedia_scraped` | Scraped from Wikipedia infobox |
| `wikipedia_single` | Single Wikipedia source, unverified |

### Phase 5 — RAG Index (`rag.py`)

Builds LlamaIndex VectorStoreIndex from all documents. Uses `SentenceSplitter` with 512 token chunks and 64 token overlap. Embeddings via `nomic-embed-text`. Index persisted to `./storage`.

**Incremental updates** check manifest for new vehicles/engines since last run. Full rebuild triggered by `--full` flag or nightly pipeline.

---

## API Reference

All authenticated endpoints require `Authorization: Bearer <VEL_API_KEY>` header.

### Core

#### `POST /query`
Vel native RAG query.

```json
// Request
{ "message": "What engine does the BMW M3 E46 use?" }

// Response
{
  "response": "The BMW M3 E46 uses the BMW S54B32 engine, producing 338hp. Data: wikipedia_scraped.",
  "response_time": 18.4
}
```

#### `POST /v1/chat/completions`
OpenAI-compatible endpoint. Used by Open WebUI.

```json
// Request
{
  "messages": [{"role": "user", "content": "What is the displacement of the 2JZ-GTE?"}],
  "stream": false,
  "model": "vel"
}
```

Supports `"stream": true` for Server-Sent Events streaming.

#### `POST /optimize`
Physics-based optimization engine.

```json
// Request
{
  "query": "I want 500whp from my Toyota Supra MK4 2JZ-GTE",
  "budget_usd": 8000
}

// Response
{
  "plan": "OPTIMIZATION PLAN — Toyota Supra Mk4 (Toyota 2JZ-GTE)\n..."
}
```

Supports three goal types:
- **Performance** — `"I want 500whp"`, `"I want to make more power"`
- **Efficiency** — `"better fuel economy"`, `"improve mpg"`
- **Handling** — `"better handling"`, `"improve cornering"`

#### `POST /reload`
Hot-reload RAG index from disk without restarting the service.

```bash
curl -s -X POST http://localhost:8001/reload \
  -H "Authorization: Bearer $VEL_API_KEY"
```

### Info

#### `GET /health`
```json
{
  "status": "ok",
  "model": "mistral",
  "index_loaded": true,
  "persist_dir": "/home/_homeos/engine-analysis/storage"
}
```

#### `GET /stats`
```json
{ "total_queries": 142, "last_query": "2026-04-10 14:52:48 - Q: What cars use the RB26..." }
```

#### `GET /v1/models`
```json
{ "data": [{"id": "vel", "object": "model", "owned_by": "aveltura"}] }
```

### Visualization

#### `GET /viz/list`
Returns list of generated chart HTML files.

#### `POST /viz/scatter`
```json
{ "x": "displacement", "y": "power_hp", "title": "Displacement vs Power" }
```

#### `POST /viz/bar`
```json
{ "spec": "power_hp", "top_n": 15 }
```

#### `POST /viz/histogram`
```json
{ "spec": "compression_ratio" }
```

#### `POST /viz/compare`
```json
{ "engines": ["Toyota 2JZ-GTE", "Nissan RB26DETT"], "spec": "power_hp" }
```

### Statistics

#### `GET /stats/specs`
Returns list of available numeric spec columns.

#### `POST /stats/correlation`
```json
{ "spec1": "displacement", "spec2": "power_hp" }
```

#### `POST /stats/outliers`
```json
{ "spec": "power_hp" }
```

#### `POST /stats/summary`
```json
{ "spec": "compression_ratio" }
```

#### `POST /stats/regression`
```json
{ "target": "power_hp", "predictors": ["displacement", "compression_ratio"] }
```

---

## Optimization Engine

### How it works

```
User query
  ├─ detect_goal_type()      → performance | efficiency | handling
  ├─ extract_car_from_query() → "Toyota Supra MK4"
  ├─ extract_engine_from_query() → "2JZ-GTE"
  │
  ├─ load_car_specs()        → pulls from engine_applications.csv + engine_normalized.csv
  │                            stock_hp, displacement, compression, drivetrain layout
  │
  ├─ Physics engine
  │   ├─ calc_crank_hp_from_whp()    → accounts for drivetrain loss (RWD 15%, AWD 18%, FWD 13%)
  │   ├─ calc_safe_boost()           → max safe PSI for stock compression ratio
  │   ├─ calc_turbo_hp_potential()   → thermodynamic model: displacement × pressure ratio × VE
  │   ├─ calc_injector_size_needed() → cc/min per cylinder at 80% duty cycle
  │   └─ calc_fuel_pump_needed()     → LPH with 20% safety margin
  │
  ├─ solve_performance_build()  → selects mods from knowledge base
  │   ├─ Turbo — smallest that meets target (best spool)
  │   ├─ Intercooler — engine-specific first, universal fallback
  │   ├─ Injectors — minimum size that meets calculated cc/min
  │   ├─ Fuel pump — minimum LPH with headroom
  │   ├─ ECU — platform-specific plug-in first, universal fallback
  │   ├─ Internals — added if target exceeds safe stock boost potential
  │   └─ Exhaust — platform-specific if available
  │
  └─ build_phases()          → groups mods into monthly budget phases at $1,500/month default
```

### Physics constants

| Parameter | Value | Notes |
|-----------|-------|-------|
| RWD drivetrain loss | 15% | Standard RWD |
| AWD drivetrain loss | 18% | Higher due to centre diff |
| FWD drivetrain loss | 13% | No rear diff |
| Injector duty cycle | 80% | Maximum safe continuous |
| Fuel cc/hp (pump) | 5.5 cc/min | E10 pump gas |
| Fuel cc/hp (E85) | 8.5 cc/min | E85 requires ~35% more fuel |
| Pump safety margin | 20% | Always size pump larger |
| NA baseline hp/L | 90 hp/L | Used in boost potential calc |

### Knowledge base (`mod_knowledge_base.py`)

| Category | Count | Examples |
|----------|-------|---------|
| Turbos | 13 | Garrett G25-660, BorgWarner EFR 8374, HKS GTIII-RS |
| Superchargers | 5 | Whipple W175FF, Magnuson TVS2300, Kraftwerks C30-94 |
| Intercoolers | 5 | Mishimoto universal, Perrin STI kit, HKS Supra R-type |
| Injectors | 3 | ID725, ID1050x, Bosch EV14 |
| Fuel pumps | 3 | Walbro 450, Bosch 044, DeatschWerks DW300C |
| Pistons | 3 | Wiseco 2JZ, CP EJ25, JE LS |
| Rods | 2 | Manley 2JZ, Brian Crower EJ |
| Head studs | 3 | ARP 2JZ/EJ/LS |
| Coilovers | 4 | BC Racing BR, KW V3, Tein Flex Z, Öhlins R&T |
| Sway bars | 1 | Whiteline kit |
| Wheels | 3 | Enkei RPF1, Rays TE37, BBS CH-R |
| Tyres | 4 | Michelin PS4S, Cup 2, Continental EcoContact, Yokohama A052 |
| ECU | 5 | Link G4X, Haltech Elite 2500, Hondata S300, EcuTek RaceROM |
| Exhaust | 4 | HKS Supra, Borla Mustang, Tomei STI, Thermal R&D R34 |
| Brakes | 4 | Brembo GT BBK, StopTech rotors, Hawk HPS/DTC-60 |
| Cooling | 3 | Mishimoto radiator, Setrab oil cooler, Greddy turbo cooler |
| Aero | 3 | Voltex wing, APR GTC-200, front splitter |

---

## Services

All services managed by systemd. Watchdog monitors Vel and restarts on failure.

| Service | Port | Description |
|---------|------|-------------|
| `vel.service` | 8001 | Vel API — FastAPI + LlamaIndex + Mistral |
| `velframe-web.service` | 8002 | Velframe web control panel |
| `vel-dashboard` | 8003 | Plotly Dash dashboard (manual start) |
| `open-webui` (Docker) | 8080 | Open WebUI — connected to Vel |
| `vel-watchdog.service` | — | Monitors vel.service, restarts on failure |
| `vel-scraper.timer` | — | Triggers full pipeline at midnight |
| `ollama` | 11434 | Mistral 7B + nomic-embed-text |
| Cockpit | 9090 | System monitoring |

### Nightly pipeline order

```
backup.py
  → manufacturer_discovery.py
  → generation_scraper.py
  → car_cleaner.py
  → scraper.py
  → cleaner.py
  → normalizer.py
  → ingest_applications.py
  → rag.py --full
  → tableau_export.py
  → viz_engine.py
  → POST /reload
```

### Common commands

```bash
# Check service status
sudo systemctl status vel.service

# Restart Vel
sudo systemctl restart vel.service

# Watch pipeline log
tail -f /home/_homeos/engine-analysis/pipeline.log

# Watch query log
tail -f /home/_homeos/engine-analysis/query.log

# Run pipeline manually
cd /home/_homeos/engine-analysis
python manufacturer_discovery.py && python generation_scraper.py && \
python car_cleaner.py && python scraper.py && python cleaner.py && \
python normalizer.py && python rag.py --full && \
curl -s -X POST http://localhost:8001/reload \
  -H "Authorization: Bearer $VEL_API_KEY"

# Rebuild index only
python rag.py --full && curl -s -X POST http://localhost:8001/reload \
  -H "Authorization: Bearer $VEL_API_KEY"

# Test a query
curl -s -X POST http://localhost:8001/query \
  -H "Authorization: Bearer $VEL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "What engine does the Toyota Supra MK4 use?"}' | python3 -m json.tool

# Test optimization
curl -s -X POST http://localhost:8001/optimize \
  -H "Authorization: Bearer $VEL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "I want 500whp from my Supra MK4"}' | python3 -m json.tool
```

---

## File Reference

```
engine-analysis/
│
├── Core API
│   ├── server.py                  Vel FastAPI server — all endpoints
│   ├── rag.py                     RAG index builder — vehicle-first documents
│   ├── optimization_engine.py     Physics-based mod optimization
│   └── mod_knowledge_base.py      80+ parts with specs, compatibility, cost
│
├── Data Pipeline
│   ├── manufacturer_discovery.py  Manufacturer → car model discovery (45 seeds)
│   ├── generation_scraper.py      Car → generation/trim scraper
│   ├── car_cleaner.py             Validation, dedup, confidence merge
│   ├── scraper.py                 Engine deep spec scraper (bore, stroke, etc.)
│   ├── cleaner.py                 Engine spec cleaner
│   ├── normalizer.py              Unit conversion, two-stream output
│   ├── ingest_applications.py     Ingest vehicle applications into RAG
│   ├── engine_code_parser.py      Displacement from engine code (2JZ → 2998cc)
│   └── epa_scraper.py             EPA displacement database scraper
│
├── Visualization
│   ├── dashboard.py               Plotly Dash dashboard (port 8003)
│   ├── viz_engine.py              Static Plotly chart generator
│   └── tableau_export.py          BI export CSV generator
│
├── Control
│   ├── velframe_web.py            Velframe web UI (port 8002)
│   ├── watchdog.py                Vel health monitor + auto-restart
│   └── backup.py                  Nightly backup to vel-backups/
│
├── Stats
│   └── stats_engine.py            Correlation, regression, outlier detection
│
├── Data Files
│   ├── verified_seeds.csv         Hand-verified engine specs (ground truth)
│   ├── engine_applications.csv    Vehicle → engine relationships
│   ├── engine_normalized.csv      Normalized engine specs
│   ├── engine_specs.csv           Raw scraped engine specs
│   ├── clean_vehicle_specs.csv    Cleaned vehicle/gen/trim data
│   ├── raw_vehicle_specs.csv      Raw scraped vehicle data
│   ├── scrape_queue.csv           Cars queued for scraping (Tier 1)
│   └── mods_specs.csv             Mod/part specs from Wikipedia
│
├── Exports
│   ├── exports/export_vehicle_engine.csv   PRIMARY — vehicle/gen/trim + engine specs joined
│   ├── exports/export_engine_specs.csv     SECONDARY — engine variant deep specs
│   └── exports/export_summary.csv          Aggregated stats by region/era/aspiration
│
├── Charts
│   └── charts/*.html              Interactive Plotly HTML charts
│
├── Storage
│   └── storage/                   LlamaIndex persisted vector index
│
├── Config
│   ├── .env                       Environment variables (VEL_API_KEY, etc.)
│   └── docker-compose.yml         Open WebUI Docker config
│
└── Logs
    ├── query.log                  All Vel queries + response times
    ├── pipeline.log               Nightly pipeline output
    ├── rag_build.log              RAG index build log
    ├── optimization.log           Optimization engine queries
    └── normalizer.log             Normalization pipeline log
```

---

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 1–6 | Foundation, Velframe, Scraper, RAG pipeline, Security | ✅ Done |
| 7 | Hardware ready — GPU acceleration, Docker Compose | ✅ Done |
| 8 | Expand knowledge — mods database, file upload ingestion | ✅ Done |
| 8.5 | Velframe web UI — browser based control panel | ✅ Done |
| 9 | Vel Chat — query without a browser, Open WebUI integration | ✅ Done |
| 10 | Math layer — scipy, statsmodels, correlation engine | ✅ Done |
| 11 | Visualization — Plotly Dash dashboard, interactive charts | ✅ Done |
| 12 | BI export — vehicle-first CSV exports, Tableau/Power BI ready | ✅ Done |
| 13 | Report generation — PDF engineering reports | 🔜 Soon |
| 14 | Universal datasets — optimize anything, not just engines | 📋 Planned |
| 15 | Autonomous learning — discovery queue, self-improving pipeline | 📋 Planned |

---

## Changelog

### April 2026 — Vehicle-First Pipeline

**Architecture:**
- Switched from engine-first to vehicle-first data model
- Every car scraped by generation and trim (Supra MK4, M3 E46, GT350 — all separate entries)
- Same engine appears multiple times across different cars at different power figures

**New files:**
- `manufacturer_discovery.py` — 45 manufacturer seeds, two-tier car discovery
- `generation_scraper.py` — generation-aware scraper, one row per vehicle/gen/trim/engine
- `car_cleaner.py` — smart duplicate merger with 4-factor confidence scoring (70/100 threshold)
- `optimization_engine.py` — physics-based mod optimization engine
- `mod_knowledge_base.py` — 80+ parts with compatibility, install location, known issues, cost

**Updated:**
- `normalizer.py` — two-stream architecture (vehicle-first + engine-first)
- `rag.py` — vehicle-first documents, BM25 weighted 2x for exact name matching
- `tableau_export.py` — `export_vehicle_engine.csv` as primary dataset
- `viz_engine.py` — vehicle-first charts (one dot per car, not per engine)
- `dashboard.py` — vehicle-first dashboard, Vehicles as primary stat
- `server.py` — tighter prompt (no hallucinations), `/optimize` endpoint, TimeoutStopSec=120
- `scraper.py` — rate limiting (0.3s API + 0.75s per engine) to avoid Wikipedia blocks
- `manufacturer_discovery.py` — tighter filtering, default tier 2 for uncertain entries

**RAG improvements:**
- Switched embeddings from Mistral → nomic-embed-text (274MB, purpose-built, 9.78 nodes/s)
- Hybrid BM25 + vector retrieval — BM25 weighted 2x via duplicate retriever in fusion
- Stricter prompt — ONLY cite vehicles in context, forbidden hedging words
- Verified data (verified_manual) correctly overrides Mistral's training knowledge

**Verified queries working:**
- `"What engine does the Toyota Supra MK4 use?"` → 2JZ-GTE, verified_manual ✅
- `"What cars came with the 2JZ-GTE?"` → Supra A80 + Aristo, correct years ✅
- `"What is the displacement of the GM LS7?"` → 7011cc/505hp, verified_manual ✅
- `"Compare the Ford Mustang GT350 and GT500"` → Voodoo 526hp vs Trinity 662hp ✅
- `"I want 500whp from my Supra MK4"` → full mod plan, $5,600-$8,870 ✅

---

## License

Personal homelab project. Not affiliated with any manufacturer or parts brand mentioned.

---

*Built on a repurposed HP ZBook. Runs at midnight. Gets smarter while you sleep.*

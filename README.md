# Aveltura — Vel

An AI that runs on scraped, messy real-world data.

I built ingestion pipelines — a cleaner, a normalizer, and ingestion scripts — that feed into a RAG interface so the AI is actually user-accessible. Started as a way to optimize a personal car build. Turned into something more general.

---

## What it does

You drop in a dataset. Vel scrapes, cleans, normalizes, indexes, and answers questions against it using RAG so the responses are grounded in your data instead of model guessing.

The whole thing rebuilds itself nightly:

```
  scrape  →  discover  →  clean  →  normalize  →  index  →  RAG query
   ↑                                                          ↓
   └────────────── runs every night ──────────────────────────┘
```

1. **Scrape** — pulls fresh data from configured sources
2. **Discover** — finds entries the index doesn't have yet
3. **Clean** — drops malformed rows, junk, duplicates
4. **Normalize** — coerces messy fields into a consistent schema
5. **Index** — rebuilds the LlamaIndex vector store
6. **Query** — RAG pulls relevant chunks, hands them to the LLM as context

Steps 1–5 run on a watchdog every night. Step 6 happens whenever you ask Vel something.

---

## Current dataset — performance engines

Started with engine specs across JDM, American, and European platforms — bore, stroke, block material, compression ratio, HP, torque, mod compatibility, dyno results.

Vel can compare engines, recommend mods for a target outcome, and explain why one engine handles boost better than another. All grounded in the indexed specs, not hallucinated.

It was the proving ground. The pipeline works on anything with measurable variables.

---

## Stack

| Layer        | Tool                                |
|--------------|-------------------------------------|
| LLM          | Mistral 7B via Ollama (swappable)   |
| RAG          | LlamaIndex                          |
| API          | FastAPI + uvicorn                   |
| Chat UI      | Open WebUI                          |
| Control TUI  | Textual (`velframe`)                |
| Remote       | Tailscale                           |
| Container    | Docker / docker-compose             |
| Scraping     | Custom Python scrapers per source   |

LLM is config-driven. Mistral 7B is what I use locally. Same pipeline runs against any Ollama model or a hosted endpoint, and the docker stack ports straight to AWS or Azure with no code changes.

---

## Velframe

Textual TUI for running the stack over SSH. One command, full ops view:

- Live status of every service
- Tail logs per service
- Restart services
- Trigger scrapers (one or full pipeline)
- Query history
- Host stats (CPU, mem, disk, GPU)

No GUI required. Plays well headless.

---

## Roadmap

Phases 1–6 shipped: ingestion, normalization, RAG query, nightly rebuild, Velframe TUI, web UI.

Coming up:

- **7** — stats layer (`scipy`, `statsmodels`)
- **8** — viz layer (`plotly`, `matplotlib`)
- **9** — Tableau export
- **10** — auto-generated PDF reports
- **11** — universal dataset support
- **12+** — domain spinoffs:
  - **FieldTech** — diagnostic tool for HVAC and appliance techs
  - **MechAI** — automotive diagnostics with OBD2 integration

End state: drop in any dataset, get back analysis, charts, exports, and a written report.

---

## Setup

```bash
git clone https://github.com/steviehp/aveltura.git
cd aveltura
cp .env.example .env
# fill in .env values
docker compose up -d
```

Full setup guide coming with Phase 7.

---

## Code

Single Python codebase. The main pieces:

- `server.py` — FastAPI entrypoint
- `rag.py` — retrieval + generation
- `index_manager.py` — vector index lifecycle
- `ingest.py` — ingestion orchestrator
- `normalizer.py` / `cleaner.py` — data hygiene
- `*_scraper.py` — scrapers per source
- `velframe.py` — control panel
- `watchdog.py` — nightly rebuild scheduler

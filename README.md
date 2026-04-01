# Aveltura — Vel

> A mathematical optimizer you can actually talk to.

## What is this?

You drop in data. Vel scans it, figures out what can be better, tells you how and why, and backs it up with graphs, tables, and full reports. No cloud. No subscription. Runs on hardware you own.

Started as a way to optimize car engines. Turned into something way bigger.

## How it works

Vel uses a RAG (Retrieval Augmented Generation) pipeline — basically it reads your data first, then answers questions about it using that data as context instead of just guessing. So when you ask it something, it's pulling from YOUR dataset not just vibes from the internet.

Every night at midnight it:
1. Scrapes fresh data from the web
2. Discovers new entries it doesn't have yet
3. Cleans out garbage rows
4. Rebuilds its knowledge base automatically

It gets smarter while you sleep.

## Current focus — Engines

Right now Vel knows about a wide range of performance engines — JDM, American muscle, European — with specs like bore, stroke, block material, compression ratio, HP and torque figures. Ask it to compare engines, suggest modifications, or explain why one engine handles boost better than another and it'll give you actual data backed answers.

Coming soon: third party mods, tuning data, dyno results.

## Tech stack

- **Mistral 7B** via Ollama — the brain
- **LlamaIndex** — RAG pipeline
- **FastAPI + uvicorn** — API server
- **Open WebUI** — chat interface
- **Textual** — Velframe TUI control panel
- **Tailscale** — remote access from anywhere
- Runs on a repurposed HP ZBook with an i7-9850H and 23GB RAM

## Velframe

Control panel for the whole stack. SSH in, type `velframe` and you get:
- Live status of every service
- Real time logs per service
- Restart buttons
- Scraper controls with full pipeline button
- Query history
- System stats

## Roadmap

This is just Phase 1-6 of a 15 phase project. End goal is a universal optimizer — drop in any dataset, ask Vel to optimize it, get back graphs, Tableau exports, and a full engineering report explaining every recommendation.

Engines are just the first dataset.

**Upcoming:**
- Mathematical stats layer (scipy, statsmodels)
- Visualization layer (plotly, matplotlib)  
- Tableau export
- PDF report generation
- Universal dataset support (anything with measurable variables)
- FieldTech — sister product for HVAC and appliance techs
- MechAI — car diagnostics with OBD2 integration

## Setup

Clone the repo, copy `.env.example` to `.env` and fill in your values, install dependencies, run the services.

Full setup guide coming soon.

## Why

Needed a way to optimize an SC300 build. Ended up building a universal optimization engine. Classic.

---

*Aveltura — built different*

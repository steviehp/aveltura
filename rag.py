"""
rag.py — Vel RAG index builder

Vehicle-first document architecture:
  Primary docs  — one per vehicle/generation/trim from engine_applications.csv
  Secondary docs — one per engine variant from engine_normalized.csv (deep specs)
  Tertiary docs  — one per mod from mods_specs.csv

Run modes:
  python rag.py          — incremental update
  python rag.py --full   — full rebuild from scratch
  python rag.py --query "your question"  — test query
"""

import os
import sys
import argparse
import logging
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Document,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.prompts import PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings

from index_manager import (
    load_manifest,
    save_manifest,
    get_new_entries,
    rotate_storage,
    update_manifest,
)

load_dotenv()

BASE_DIR        = os.getenv("BASE_DIR",        "/home/_homeos/engine-analysis")
MODEL_NAME      = os.getenv("MODEL_NAME",      "mistral")
EMBED_MODEL     = os.getenv("EMBED_MODEL",     "nomic-embed-text")
PERSIST_DIR     = os.getenv("PERSIST_DIR",     os.path.join(BASE_DIR, "storage"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))

APPLICATIONS_CSV = os.path.join(BASE_DIR, "engine_applications.csv")
NORMALIZED_CSV   = os.path.join(BASE_DIR, "engine_normalized.csv")
MODS_CSV         = os.path.join(BASE_DIR, "mods_specs.csv")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "rag_build.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

Settings.llm         = Ollama(model=MODEL_NAME, request_timeout=REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL)

# ── Vel QA prompt ─────────────────────────────────────────────────────────────
VEL_QA_PROMPT = PromptTemplate(
    "You are Vel, an expert automotive engine analysis AI. "
    "You have deep knowledge of engine specifications, vehicle applications, "
    "tuning, and performance data.\n\n"
    "The following context was retrieved from the Vel engine database:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "Instructions:\n"
    "1. Use your own automotive knowledge to answer the question accurately.\n"
    "2. If the context above contains relevant verified data, prioritize and "
    "cite it over your general knowledge — especially for specific power figures, "
    "displacement, or tune details marked as verified_manual.\n"
    "3. If you are genuinely uncertain about specific technical details and the "
    "context does not help, say: 'I don't have verified data on that — "
    "adding it to the discovery queue for the next scrape run.'\n"
    "4. Never refuse to answer a question about a well-known engine or car. "
    "Use your training knowledge as a baseline.\n\n"
    "Question: {query_str}\n"
    "Answer:"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(val, unit=""):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        f = float(val)
        if f == int(f):
            return f"{int(f)}{unit}"
        return f"{round(f, 1)}{unit}"
    except Exception:
        return str(val)


# ── Document builders ─────────────────────────────────────────────────────────

def build_vehicle_documents(apps_df):
    """
    PRIMARY documents — one per vehicle/generation/trim row.

    Each doc answers questions like:
      "What engine does the BMW M3 E46 use?"
      "How much power does the Supra MK4 make?"
      "What Mustangs have over 500hp?"

    The vehicle name is repeated prominently so BM25 finds it by name.
    """
    documents = []

    for _, row in apps_df.iterrows():
        vehicle    = str(row.get("vehicle", "")).strip()
        engine     = str(row.get("engine",  "")).strip()
        generation = str(row.get("generation", "")).strip()
        trim       = str(row.get("trim", "")).strip()
        mfr        = str(row.get("manufacturer", "")).strip()

        if not vehicle:
            continue

        # Build display label
        parts = [vehicle]
        if generation and generation not in ("base", "nan", ""):
            parts.append(generation)
        if trim and trim not in ("base", "nan", ""):
            parts.append(trim)
        label = " — ".join(parts)

        year_start = row.get("year_start")
        year_end   = row.get("year_end")
        power_hp   = _fmt(row.get("power_hp"), "hp")
        torque_nm  = _fmt(row.get("torque_nm"), "Nm")
        disp       = row.get("displacement") or row.get("displacement_cc")
        disp_str   = ""
        if disp and not pd.isna(disp):
            disp_cc = float(disp)
            disp_str = f"{int(disp_cc)}cc ({round(disp_cc/1000, 1)}L)"

        year_str = ""
        if year_start and not pd.isna(year_start):
            if year_end and not pd.isna(year_end):
                year_str = f"{int(year_start)}–{int(year_end)}"
            else:
                year_str = f"{int(year_start)}–present"

        confidence = str(row.get("confidence", "wikipedia_scraped"))
        notes      = str(row.get("notes", "")) if pd.notna(row.get("notes")) else ""

        # Build document text — vehicle name repeated for BM25 signal
        lines = [
            f"Vehicle: {label}",
            f"The {label} is a {mfr} vehicle." if mfr else f"Vehicle: {label}",
        ]
        if engine and engine not in ("nan", ""):
            lines.append(f"Engine: {engine}")
            lines.append(f"The {vehicle} uses the {engine} engine.")
        if year_str:
            lines.append(f"Production years: {year_str}")
        if power_hp:
            lines.append(f"Power output: {power_hp}")
        if torque_nm:
            lines.append(f"Torque: {torque_nm}")
        if disp_str:
            lines.append(f"Displacement: {disp_str}")
        if notes and notes not in ("nan", "car_discovery", ""):
            lines.append(f"Notes: {notes}")
        lines.append(f"Data confidence: {confidence}")

        text = "\n".join(lines)

        documents.append(Document(
            text=text,
            metadata={
                "vehicle":    vehicle,
                "engine":     engine,
                "generation": generation,
                "trim":       trim,
                "confidence": confidence,
                "type":       "vehicle_spec",
            }
        ))

    logging.info(f"Built {len(documents)} vehicle documents")
    return documents


def build_engine_documents(normalized_df):
    """
    SECONDARY documents — one per engine variant (deep specs).

    Answers questions like:
      "What is the bore and stroke of the K20A?"
      "What compression ratio does the 2JZ-GTE have?"
    """
    documents = []

    for _, row in normalized_df.iterrows():
        engine     = str(row.get("engine", "")).strip()
        variant    = str(row.get("variant", "base")).strip()
        ev_label   = str(row.get("engine_variant", engine)).strip()
        confidence = str(row.get("confidence", "wikipedia_single"))

        lines = [
            f"Engine: {ev_label}",
            f"The {ev_label} is an engine made by "
            f"{engine.split()[0] if engine else 'unknown manufacturer'}.",
        ]

        disp = _fmt(row.get("displacement"), "cc")
        if disp:
            disp_l = _fmt(float(row["displacement"]) / 1000, "L") \
                if row.get("displacement") else ""
            lines.append(f"Displacement: {disp} ({disp_l})")

        hp = _fmt(row.get("power_hp"), "hp")
        if hp:
            lines.append(f"Power: {hp}")

        torque = _fmt(row.get("torque_nm"), "Nm")
        if torque:
            lines.append(f"Torque: {torque}")

        config = row.get("configuration")
        if config and not pd.isna(config):
            lines.append(f"Configuration: {config}")

        valvetrain = row.get("valvetrain")
        if valvetrain and not pd.isna(valvetrain):
            lines.append(f"Valvetrain: {valvetrain}")

        fuel = row.get("fuel_system")
        if fuel and not pd.isna(fuel):
            lines.append(f"Fuel system: {fuel}")

        bore   = _fmt(row.get("bore_mm"), "mm")
        stroke = _fmt(row.get("stroke_mm"), "mm")
        if bore and stroke:
            lines.append(f"Bore x Stroke: {bore} x {stroke}")

        compression = _fmt(row.get("compression_ratio"))
        if compression:
            lines.append(f"Compression ratio: {compression}:1")

        redline = _fmt(row.get("redline_rpm"), " rpm")
        if redline:
            lines.append(f"Redline: {redline}")

        block = row.get("block_material")
        if block and not pd.isna(block):
            lines.append(f"Block: {block}")

        head = row.get("head_material")
        if head and not pd.isna(head):
            lines.append(f"Head: {head}")

        production = row.get("production")
        if production and not pd.isna(production):
            lines.append(f"Production: {production}")

        lines.append(f"Data confidence: {confidence}")

        text = "\n".join(lines)

        documents.append(Document(
            text=text,
            metadata={
                "engine":     engine,
                "variant":    variant,
                "confidence": confidence,
                "type":       "engine_spec",
            }
        ))

    logging.info(f"Built {len(documents)} engine spec documents")
    return documents


def build_mod_documents(mods_df):
    documents = []
    for mod_name, group in mods_df.groupby("mod"):
        specs = "\n".join(
            f"{row['spec']}: {row['value']}"
            for _, row in group.iterrows()
        )
        text = f"Mod/Part: {mod_name}\n{specs}"
        documents.append(Document(
            text=text,
            metadata={"mod": mod_name, "type": "mod"}
        ))
    logging.info(f"Built {len(documents)} mod documents")
    return documents


# ── Index management ──────────────────────────────────────────────────────────

def _get_parser():
    return SentenceSplitter(chunk_size=512, chunk_overlap=64)


def _insert_documents(index, documents):
    parser     = _get_parser()
    nodes      = parser.get_nodes_from_documents(documents)
    for node in tqdm(nodes, desc="Indexing", unit="node"):
        index.insert_nodes([node])
    return len(nodes)


def load_data():
    apps_df = pd.DataFrame()
    if os.path.exists(APPLICATIONS_CSV):
        apps_df = pd.read_csv(APPLICATIONS_CSV)
        print(f"Loaded {len(apps_df)} vehicle applications")
    else:
        print("No engine_applications.csv — skipping vehicle docs")

    normalized_df = pd.DataFrame()
    if os.path.exists(NORMALIZED_CSV):
        normalized_df = pd.read_csv(NORMALIZED_CSV)
        print(f"Loaded {len(normalized_df)} engine variants")
    else:
        print("No engine_normalized.csv — skipping engine spec docs")

    mods_df = pd.DataFrame()
    if os.path.exists(MODS_CSV):
        mods_df = pd.read_csv(MODS_CSV)
        print(f"Loaded {len(mods_df)} mod rows")

    return apps_df, normalized_df, mods_df


# ── Hybrid query engine ───────────────────────────────────────────────────────

def build_hybrid_query_engine(index, streaming=False):
    """
    BM25 (exact keyword) + vector (semantic) hybrid retriever.
    BM25 finds "BMW M3 E46" exactly.
    Vector finds "what BMW sports car from 2000 uses S54".
    """
    nodes = list(index.docstore.docs.values())

    bm25_retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=5,
    )
    vector_retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=5,
    )
    fusion_retriever = QueryFusionRetriever(
        retrievers=[bm25_retriever, bm25_retriever, vector_retriever],
        similarity_top_k=6,
        num_queries=1,
        mode="reciprocal_rerank",
        use_async=False,
    )
    return RetrieverQueryEngine.from_args(
        retriever=fusion_retriever,
        text_qa_template=VEL_QA_PROMPT,
        streaming=streaming,
    )


# ── Main runners ──────────────────────────────────────────────────────────────

def run_full_rebuild():
    print("Building full index from scratch...")
    logging.info("Full rebuild started")

    apps_df, normalized_df, mods_df = load_data()

    documents = []
    # Vehicle docs first — primary
    if not apps_df.empty:
        documents.extend(build_vehicle_documents(apps_df))
    # Engine spec docs — secondary (deep specs)
    if not normalized_df.empty:
        documents.extend(build_engine_documents(normalized_df))
    # Mod docs — tertiary
    if not mods_df.empty:
        documents.extend(build_mod_documents(mods_df))

    print(f"Total documents: {len(documents)}")

    index       = VectorStoreIndex(nodes=[])
    nodes_added = _insert_documents(index, documents)

    rotate_storage()
    index.storage_context.persist(persist_dir=PERSIST_DIR)

    manifest = load_manifest()
    manifest["version"]      += 1
    manifest["engines"]       = list(normalized_df["engine"].unique()) \
        if not normalized_df.empty else []
    manifest["vehicles"]      = list(apps_df["vehicle"].unique()) \
        if not apps_df.empty else []
    manifest["mods"]          = list(mods_df["mod"].unique()) \
        if not mods_df.empty else []
    manifest["full_rebuild"]  = True
    save_manifest(manifest)

    print(f"Full rebuild complete — {len(documents)} docs, {nodes_added} nodes")
    logging.info(
        f"Full rebuild complete: {len(documents)} docs, {nodes_added} nodes"
    )
    return index


def run_incremental_update():
    manifest = load_manifest()

    if not os.path.exists(PERSIST_DIR) or manifest.get("version", 0) == 0:
        print("No existing index — running full rebuild")
        return run_full_rebuild()

    print(f"Loading existing index v{manifest['version']}...")
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    index           = load_index_from_storage(storage_context)

    new_engines, new_mods = get_new_entries(manifest)

    # Also check for new vehicles
    apps_df, normalized_df, mods_df = load_data()
    known_vehicles = set(manifest.get("vehicles", []))
    new_vehicles   = []
    if not apps_df.empty and "vehicle" in apps_df.columns:
        new_vehicles = [
            v for v in apps_df["vehicle"].unique()
            if v not in known_vehicles
        ]

    if not new_engines and not new_mods and not new_vehicles:
        print("Index is up to date")
        logging.info("Incremental update: nothing to add")
        return index

    print(
        f"New vehicles: {len(new_vehicles)} | "
        f"New engines: {len(new_engines)} | "
        f"New mods: {len(new_mods)}"
    )

    documents = []

    if new_vehicles and not apps_df.empty:
        new_apps = apps_df[apps_df["vehicle"].isin(new_vehicles)]
        documents.extend(build_vehicle_documents(new_apps))

    if new_engines and not normalized_df.empty:
        new_eng_df = normalized_df[normalized_df["engine"].isin(new_engines)]
        documents.extend(build_engine_documents(new_eng_df))

    if new_mods and not mods_df.empty:
        new_mods_df = mods_df[mods_df["mod"].isin(new_mods)]
        documents.extend(build_mod_documents(new_mods_df))

    if not documents:
        print("No new documents to add")
        return index

    nodes_added = _insert_documents(index, documents)
    rotate_storage()
    index.storage_context.persist(persist_dir=PERSIST_DIR)

    update_manifest(new_engines, new_mods)
    manifest = load_manifest()
    manifest["vehicles"] = list(apps_df["vehicle"].unique()) \
        if not apps_df.empty else []
    save_manifest(manifest)

    print(
        f"Incremental update complete — "
        f"{len(documents)} new docs, {nodes_added} nodes"
    )
    logging.info(
        f"Incremental update: {len(documents)} docs, {nodes_added} nodes"
    )
    return index


def get_query_engine(index=None, streaming=False):
    if index is None:
        if not os.path.exists(PERSIST_DIR):
            print("No index found — run rag.py first")
            sys.exit(1)
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)
    return build_hybrid_query_engine(index, streaming=streaming)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vel RAG index builder")
    parser.add_argument("--full",  action="store_true", help="Force full rebuild")
    parser.add_argument("--query", type=str,            help="Test query")
    args = parser.parse_args()

    if args.full:
        index = run_full_rebuild()
    else:
        index = run_incremental_update()

    print("\nIndex ready!")

    if args.query:
        print(f"\nQuery: {args.query}")
        qe       = get_query_engine(index)
        response = qe.query(args.query)
        print(f"\nResponse:\n{response}")

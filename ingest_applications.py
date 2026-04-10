import pandas as pd
import os
from llama_index.core import Document, VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings
from dotenv import load_dotenv
from tqdm import tqdm
from index_manager import rotate_storage, load_manifest, save_manifest

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")

Settings.llm = Ollama(model=MODEL_NAME, request_timeout=300.0)
Settings.embed_model = OllamaEmbedding(model_name=MODEL_NAME)

def build_application_documents():
    path = os.path.join(BASE_DIR, "engine_applications.csv")
    if not os.path.exists(path):
        print("No engine_applications.csv found")
        return []

    df = pd.read_csv(path)
    documents = []

    # Group by engine — one doc per engine with all its applications
    for engine_name, group in df.groupby("engine"):
        apps = []
        for _, row in group.iterrows():
            app_text = f"{row['vehicle']} ({row['year_start']}-{row['year_end']}): {row['power_hp']}hp"
            if not pd.isna(row.get('torque_nm')):
                app_text += f", {row['torque_nm']}Nm torque"
            if not pd.isna(row.get('notes')):
                app_text += f" — {row['notes']}"
            apps.append(app_text)

        text = f"Engine: {engine_name}\nVehicle Applications:\n" + "\n".join(f"- {a}" for a in apps)
        documents.append(Document(
            text=text,
            metadata={"engine": engine_name, "type": "applications"}
        ))

    print(f"Created {len(documents)} application documents")
    return documents

def run_ingest_applications():
    print("Ingesting engine applications into RAG...")

    if not os.path.exists(PERSIST_DIR):
        print("No existing index found. Run rag.py first.")
        return

    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    index = load_index_from_storage(storage_context)

    documents = build_application_documents()
    if not documents:
        return

    parser = SimpleNodeParser.from_defaults()
    nodes = parser.get_nodes_from_documents(documents)

    for node in tqdm(nodes, desc="Ingesting applications", unit="node"):
        index.insert_nodes([node])

    rotate_storage()
    index.storage_context.persist(persist_dir=PERSIST_DIR)

    manifest = load_manifest()
    manifest["applications_ingested"] = True
    manifest["version"] += 1
    save_manifest(manifest)

    print(f"Done! Ingested {len(documents)} engine application documents")

if __name__ == "__main__":
    run_ingest_applications()

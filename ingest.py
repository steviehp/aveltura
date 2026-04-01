import os
import shutil
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Document
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings
from tqdm import tqdm
from index_manager import rotate_storage, load_manifest, save_manifest

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))

logging.basicConfig(
    filename="ingest.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

Settings.llm = Ollama(model=MODEL_NAME, request_timeout=REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name=MODEL_NAME)

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"

def extract_pdf(filepath):
    from pypdf import PdfReader
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_csv(filepath):
    df = pd.read_csv(filepath)
    return df.to_string()

def process_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    category = os.path.basename(os.path.dirname(filepath))

    print(f"Processing {filename} ({category})...")

    if ext == ".pdf":
        text = extract_pdf(filepath)
    elif ext == ".csv":
        text = extract_csv(filepath)
    else:
        print(f"Unsupported file type: {ext}")
        return None

    if not text.strip():
        print(f"No text extracted from {filename}")
        return None

    doc = Document(
        text=text[:50000],  # cap at 50k chars
        metadata={
            "filename": filename,
            "category": category,
            "type": "upload",
            "ingested_at": datetime.now().isoformat()
        }
    )
    logging.info(f"Processed {filename}: {len(text)} chars")
    return doc

def run_ingestion():
    print(f"Starting ingestion at {datetime.now()}")

    # Find all files in uploads
    files_to_process = []
    for root, dirs, files in os.walk(UPLOAD_DIR):
        for f in files:
            if f.endswith((".pdf", ".csv")):
                files_to_process.append(os.path.join(root, f))

    if not files_to_process:
        print("No files to ingest")
        return

    print(f"Found {len(files_to_process)} files to ingest")

    # Load existing index
    if os.path.exists(PERSIST_DIR):
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)
    else:
        print("No existing index found, create one first with rag.py")
        return

    # Process each file
    documents = []
    processed_files = []
    for filepath in files_to_process:
        doc = process_file(filepath)
        if doc:
            documents.append(doc)
            processed_files.append(filepath)

    if not documents:
        print("No documents extracted")
        return

    # Index new documents
    parser = SimpleNodeParser.from_defaults()
    nodes = parser.get_nodes_from_documents(documents)
    for node in tqdm(nodes, desc="Ingesting", unit="node"):
        index.insert_nodes([node])

    # Rotate storage and save
    rotate_storage()
    index.storage_context.persist(persist_dir=PERSIST_DIR)

    # Update manifest
    manifest = load_manifest()
    if "uploads" not in manifest:
        manifest["uploads"] = {}
    for filepath in processed_files:
        manifest["uploads"][os.path.basename(filepath)] = datetime.now().isoformat()
    manifest["version"] += 1
    save_manifest(manifest)

    # Move processed files
    for filepath in processed_files:
        dest = os.path.join(PROCESSED_DIR, os.path.basename(filepath))
        shutil.move(filepath, dest)
        print(f"Moved {os.path.basename(filepath)} to processed/")

    print(f"Ingestion complete — {len(documents)} documents added to Vel")
    logging.info(f"Ingested {len(documents)} documents")

if __name__ == "__main__":
    run_ingestion()

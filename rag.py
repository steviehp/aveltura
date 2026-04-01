from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Document
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings
from dotenv import load_dotenv
from tqdm import tqdm
from index_manager import load_manifest, save_manifest, get_new_entries, rotate_storage, update_manifest
import pandas as pd
import os

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")
DATA_FILE = os.getenv("DATA_FILE", "engine_specs.csv")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))

Settings.llm = Ollama(model=MODEL_NAME, request_timeout=REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name=MODEL_NAME)

manifest = load_manifest()
new_engines, new_mods = get_new_entries(manifest)

if os.path.exists(PERSIST_DIR) and manifest["version"] > 0:
    print(f"Loading existing index v{manifest['version']}...")
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    index = load_index_from_storage(storage_context)

    if new_engines or new_mods:
        print(f"Found {len(new_engines)} new engines and {len(new_mods)} new mods, updating incrementally...")
        documents = []

        if new_engines:
            df = pd.read_csv(DATA_FILE)
            for engine_name in new_engines:
                group = df[df["engine"] == engine_name]
                specs = "\n".join(f"{row['spec']}: {row['value']}" for _, row in group.iterrows())
                text = f"Engine: {engine_name}\n{specs}"
                documents.append(Document(text=text, metadata={"engine": engine_name, "type": "engine"}))

        if new_mods:
            mods_df = pd.read_csv("mods_specs.csv")
            for mod_name in new_mods:
                group = mods_df[mods_df["mod"] == mod_name]
                specs = "\n".join(f"{row['spec']}: {row['value']}" for _, row in group.iterrows())
                text = f"Mod: {mod_name}\n{specs}"
                documents.append(Document(text=text, metadata={"mod": mod_name, "type": "mod"}))

        parser = SimpleNodeParser.from_defaults()
        nodes = parser.get_nodes_from_documents(documents)
        for node in tqdm(nodes, desc="Incremental indexing", unit="node"):
            index.insert_nodes([node])

        rotate_storage()
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        update_manifest(new_engines, new_mods)
        print("Incremental update complete")
    else:
        print("No new data found, index is up to date")

else:
    print("Building full index from scratch...")
    df = pd.read_csv(DATA_FILE)
    documents = []

    engines = list(df.groupby("engine"))
    for engine_name, group in engines:
        specs = "\n".join(f"{row['spec']}: {row['value']}" for _, row in group.iterrows())
        text = f"Engine: {engine_name}\n{specs}"
        documents.append(Document(text=text, metadata={"engine": engine_name, "type": "engine"}))
    print(f"Created {len(documents)} engine documents")

    if os.path.exists("mods_specs.csv"):
        mods_df = pd.read_csv("mods_specs.csv")
        mods_list = list(mods_df.groupby("mod"))
        for mod_name, group in mods_list:
            specs = "\n".join(f"{row['spec']}: {row['value']}" for _, row in group.iterrows())
            text = f"Mod: {mod_name}\n{specs}"
            documents.append(Document(text=text, metadata={"mod": mod_name, "type": "mod"}))
        print(f"Created {len(mods_list)} mod documents")

    print(f"Total documents: {len(documents)}")
    parser = SimpleNodeParser.from_defaults()
    nodes = parser.get_nodes_from_documents(documents)
    index = VectorStoreIndex(nodes=[])
    for node in tqdm(nodes, desc="Indexing", unit="node"):
        index.insert_nodes([node])

    rotate_storage()
    index.storage_context.persist(persist_dir=PERSIST_DIR)
    update_manifest(
        list(df["engine"].unique()),
        list(pd.read_csv("mods_specs.csv")["mod"].unique()) if os.path.exists("mods_specs.csv") else []
    )

print("Index ready!")
query_engine = index.as_query_engine()
response = query_engine.query("What Garrett turbo works best with a 2JZ-GTE build?")
print(response)

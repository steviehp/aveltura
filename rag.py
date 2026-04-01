from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Document
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings
from dotenv import load_dotenv
from tqdm import tqdm
import pandas as pd
import os

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")
DATA_FILE = os.getenv("DATA_FILE", "engine_specs.csv")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))

Settings.llm = Ollama(model=MODEL_NAME, request_timeout=REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name=MODEL_NAME)

if os.path.exists(PERSIST_DIR):
    print("Loading existing index...")
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    index = load_index_from_storage(storage_context)
else:
    print("Building new index...")
    df = pd.read_csv(DATA_FILE)
    documents = []
    engines = list(df.groupby("engine"))
    for engine_name, group in engines:
        specs = "\n".join(f"{row['spec']}: {row['value']}" for _, row in group.iterrows())
        text = f"Engine: {engine_name}\n{specs}"
        documents.append(Document(text=text, metadata={"engine": engine_name}))
    print(f"Created {len(documents)} engine documents")
    parser = SimpleNodeParser.from_defaults()
    nodes = parser.get_nodes_from_documents(documents)
    index = VectorStoreIndex(nodes=[])
    for node in tqdm(nodes, desc="Indexing", unit="node"):
        index.insert_nodes([node])
    index.storage_context.persist(persist_dir=PERSIST_DIR)

print("Index ready!")
query_engine = index.as_query_engine()

response = query_engine.query("Compare the 2JZ-GTE and LS3 for forced induction potential")
print(response)

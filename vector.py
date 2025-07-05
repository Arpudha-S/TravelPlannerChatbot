import uuid
import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.PersistentClient(path="./vector_store")
collection = client.get_or_create_collection("travel_docs")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text):
    return embedder.encode([text], normalize_embeddings=True)[0]

def split_text_into_chunks(text, max_length=300):
    sentences = text.split('.')
    chunks = []
    chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(chunk) + len(sentence) < max_length:
            chunk += sentence + ". "
        else:
            chunks.append(chunk.strip())
            chunk = sentence + ". "
    if chunk:
        chunks.append(chunk.strip())

    return [c for c in chunks if c]

def add_to_vector_db(text, doc_id, category="brochure"):
    chunks = split_text_into_chunks(text)  # Assuming you chunk text
    embeddings = [embed(chunk) for chunk in chunks]
    collection.add(
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"doc_id": doc_id, "category": category}] * len(chunks),
        ids=[str(uuid.uuid4()) for _ in chunks]
    )

def search_vector_db(query, top_k=3, doc_id_filter=None, category_filter=None):
    embedding = embed(query)
    where_clause = {}
    
    if doc_id_filter:
        where_clause['doc_id'] = doc_id_filter
    if category_filter:
        where_clause['category'] = category_filter

    query_args = {
        "query_embeddings": [embedding],
        "n_results": top_k,
    }
    
    if where_clause:
        query_args["where"] = where_clause

    results = collection.query(**query_args)

    return [
        {"text": doc, "metadata": meta}
        for doc, meta in zip(results['documents'][0], results['metadatas'][0])
    ]

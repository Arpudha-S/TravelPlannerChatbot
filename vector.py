import uuid
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

# Initialize
embedder = SentenceTransformer("all-MiniLM-L6-v2")
VECTOR_DIM = 384  # For "all-MiniLM-L6-v2"
client = QdrantClient(":memory:")

# Create collection
COLLECTION_NAME = "travel_docs"
client.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
)

def embed(text):
    return embedder.encode([text], normalize_embeddings=True)[0].tolist()

def split_text_into_chunks(text, max_length=300):
    sentences = text.split('.')
    chunks, chunk = [], ""
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
    chunks = split_text_into_chunks(text)
    embeddings = [embed(chunk) for chunk in chunks]
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={"doc_id": doc_id, "category": category, "document": chunk}
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"Added {len(points)} chunks to Qdrant vector DB.")

def search_vector_db(query, top_k=3, doc_id_filter=None, category_filter=None):
    vector = embed(query)
    filters = []
    if doc_id_filter:
        filters.append(FieldCondition(key="doc_id", match=MatchValue(value=doc_id_filter)))
    if category_filter:
        filters.append(FieldCondition(key="category", match=MatchValue(value=category_filter)))

    query_filter = Filter(must=filters) if filters else None

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=top_k,
        query_filter=query_filter
    )
    return [
        {"text": r.payload.get("document", ""), "metadata": {k: v for k, v in r.payload.items() if k != "document"}}
        for r in results
    ]

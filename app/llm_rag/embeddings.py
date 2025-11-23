from typing import List, Dict, Any, Tuple
import os
import json
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
import psycopg2
from psycopg2.extras import execute_values

class VectorStoreWrapper:
	def __init__(self, db_url: str, embedding_model: HuggingFaceEmbeddings):
		self.db_url = db_url
		self.embedding_model = embedding_model

	def _get_connection(self):
		return psycopg2.connect(self.db_url)

	def search(self, query: str, k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
		"""Search for similar embeddings using pgvector."""
		query_embedding = self.embedding_model.embed_query(query)
		
		with self._get_connection() as conn:
			with conn.cursor() as cur:
				cur.execute("""
					SELECT id, content, metadata, 
					       1 - (embedding <=> %s::vector) as similarity
					FROM embeddings
					ORDER BY embedding <=> %s::vector
					LIMIT %s
				""", (json.dumps(query_embedding), json.dumps(query_embedding), k))
				
				results = []
				for row in cur.fetchall():
					doc_id, content, metadata, similarity = row
					doc_dict = {
						"id": doc_id,
						"content": content,
						"start_row": metadata.get("start_row"),
						"end_row": metadata.get("end_row")
					}
					results.append((doc_dict, float(similarity)))
				return results

def build_vector_store(chunks: List[Dict[str, Any]]) -> VectorStoreWrapper:
	model_name = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
	db_url = os.getenv("DATABASE_URL")
	
	if not db_url:
		raise ValueError("DATABASE_URL environment variable required for vector store")
	
	embeddings = HuggingFaceEmbeddings(model_name=model_name)
	
	# Batch insert embeddings
	with psycopg2.connect(db_url) as conn:
		with conn.cursor() as cur:
			# Generate embeddings for all chunks
			texts = [c["content"] for c in chunks]
			vectors = embeddings.embed_documents(texts)
			
			# Prepare data for batch insert
			data = [
				(
					c["id"],
					c["content"],
					json.dumps(v),
					json.dumps({"start_row": c["start_row"], "end_row": c["end_row"]})
				)
				for c, v in zip(chunks, vectors)
			]
			
			# Upsert embeddings
			execute_values(
				cur,
				"""
				INSERT INTO embeddings (id, content, embedding, metadata)
				VALUES %s
				ON CONFLICT (id) DO UPDATE SET
					content = EXCLUDED.content,
					embedding = EXCLUDED.embedding,
					metadata = EXCLUDED.metadata
				""",
				data,
				template="(%s, %s, %s::vector, %s::jsonb)"
			)
		conn.commit()
	
	return VectorStoreWrapper(db_url, embeddings)

def load_vector_store(persist_dir: str = ".vectorstore") -> VectorStoreWrapper:
	"""
	Load existing vector store from PostgreSQL database.
	persist_dir parameter kept for backward compatibility but ignored.
	"""
	model_name = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
	db_url = os.getenv("DATABASE_URL")
	
	if not db_url:
		raise ValueError("DATABASE_URL environment variable required for vector store")
	
	embeddings = HuggingFaceEmbeddings(model_name=model_name)
	return VectorStoreWrapper(db_url, embeddings)


from typing import List, Dict, Any, Tuple
import os
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class VectorStoreWrapper:
	def __init__(self, store: Chroma, doc_map: Dict[str, Dict[str, Any]]):
		self.store = store
		self.doc_map = doc_map

	def search(self, query: str, k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
		results = self.store.similarity_search_with_relevance_scores(query, k=k)
		out: List[Tuple[Dict[str, Any], float]] = []
		for doc, score in results:
			meta = self.doc_map.get(doc.metadata.get("id"), {})
			out.append((meta, float(score)))
		return out

def build_vector_store(chunks: List[Dict[str, Any]]) -> VectorStoreWrapper:
	model_name = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
	docs: List[Document] = []
	doc_map: Dict[str, Dict[str, Any]] = {}
	for c in chunks:
		doc = Document(page_content=c["content"], metadata={"id": c["id"], "start_row": c["start_row"], "end_row": c["end_row"]})
		docs.append(doc)
		doc_map[c["id"]] = c
	persist_dir = os.getenv("VECTORSTORE_DIR", ".vectorstore")
	try:
		embeddings = HuggingFaceEmbeddings(model_name=model_name)
		store = Chroma.from_documents(docs, embedding=embeddings, persist_directory=persist_dir)
		return VectorStoreWrapper(store, doc_map)
	except Exception:
		# Fallback to in-memory TF-IDF if embedding model load fails
		tfidf = TfidfVectorizer(min_df=1)
		matrix = tfidf.fit_transform([d.page_content for d in docs])
		class FallbackStore(VectorStoreWrapper):
			def __init__(self):
				self.doc_map = doc_map
			def search(self, query: str, k: int = 5):
				qv = tfidf.transform([query])
				sims = cosine_similarity(qv, matrix)[0]
				scored = list(zip(docs, sims))
				scored.sort(key=lambda x: x[1], reverse=True)
				out: List[Tuple[Dict[str, Any], float]] = []
				for doc, score in scored[:k]:
					out.append((self.doc_map.get(doc.metadata.get("id"), {}), float(score)))
				return out
		return FallbackStore()

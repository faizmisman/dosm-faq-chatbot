"""RAG asset builder

Populates PostgreSQL embeddings table from a tabular DOSM dataset.

Usage:
  python train/train_rag_assets.py --input path/to/data.csv
  # optionally specify model
  python train/train_rag_assets.py --input data.csv \
	--model sentence-transformers/all-MiniLM-L6-v2

Environment requirements:
  DATABASE_URL = PostgreSQL connection string (required)
  INPUT_DATASET = path to dataset if --input not provided
  EMBEDDING_MODEL_NAME = model name if --model not provided
  MLFLOW_TRACKING_URI = MLflow server URL (optional, defaults to local mlruns/)

Outputs:
  - Embeddings inserted into PostgreSQL embeddings table
  - MLflow run with metrics and parameters
  - chunks.json metadata for traceability (optional, via --metadata-dir)
  - summary.json with basic statistics (optional, via --metadata-dir)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import mlflow

from app.llm_rag.chunking import load_dataset, build_chunks
from app.llm_rag.embeddings import build_vector_store

def parse_args():
	ap = argparse.ArgumentParser()
	ap.add_argument("--input", help="Path to dataset CSV", default=os.getenv("INPUT_DATASET"))
	ap.add_argument("--metadata-dir", help="Optional directory to output metadata JSON files", default=None)
	ap.add_argument("--model", help="Embedding model name", default=os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"))
	ap.add_argument("--chunk-size", type=int, default=25, help="Rows per chunk")
	return ap.parse_args()

def main():
	args = parse_args()
	if not args.input:
		print("[error] --input or INPUT_DATASET required", file=sys.stderr)
		return 2
	if not os.path.exists(args.input):
		print(f"[error] input dataset not found: {args.input}", file=sys.stderr)
		return 2
	
	db_url = os.getenv("DATABASE_URL")
	if not db_url:
		print("[error] DATABASE_URL environment variable required", file=sys.stderr)
		return 2

	# Setup MLflow
	mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "mlruns")
	mlflow.set_tracking_uri(mlflow_uri)
	mlflow.set_experiment("rag-ingestion")
	
	run_date = datetime.utcnow().strftime("%Y-%m-%d")
	
	with mlflow.start_run(run_name=f"ingest_{run_date}"):
		os.environ["EMBEDDING_MODEL_NAME"] = args.model
		
		# Log parameters
		mlflow.log_param("run_date", run_date)
		mlflow.log_param("dataset_path", args.input)
		mlflow.log_param("embedding_model", args.model)
		mlflow.log_param("chunk_size", args.chunk_size)
		mlflow.log_param("database", "postgresql")

		print(f"[info] Loading dataset: {args.input}")
		df = load_dataset(args.input)
		print(f"[info] Rows: {len(df)} Columns: {list(df.columns)}")
		
		# Log dataset metrics
		mlflow.log_metric("row_count", len(df))
		mlflow.log_metric("column_count", len(df.columns))
		
		chunk_size = max(1, args.chunk_size)
		chunks = build_chunks(df, chunk_size=chunk_size)
		print(f"[info] Built {len(chunks)} chunks (chunk_size={chunk_size})")
		
		# Log chunking metrics
		mlflow.log_metric("chunk_count", len(chunks))
		avg_chunk_length = sum(len(c['content']) for c in chunks) / len(chunks) if chunks else 0
		mlflow.log_metric("avg_chunk_length", avg_chunk_length)

		print(f"[info] Building vector store with model {args.model}")
		print(f"[info] Inserting embeddings into PostgreSQL database")
		store_wrapper = build_vector_store(chunks)
		print(f"[done] Inserted {len(chunks)} embeddings into database")
		
		# Log final metrics
		mlflow.log_metric("embeddings_inserted", len(chunks))
		mlflow.log_metric("embedding_dimension", 384)  # all-MiniLM-L6-v2 dimension

		# Save metadata if output directory specified
		if args.metadata_dir:
			out_dir = Path(args.metadata_dir)
			out_dir.mkdir(parents=True, exist_ok=True)
			
			with (out_dir / "chunks.json").open("w", encoding="utf-8") as f:
				json.dump(chunks, f, ensure_ascii=False, indent=2)
			summary = {
				"timestamp": datetime.utcnow().isoformat() + "Z",
				"rows": len(df),
				"chunks": len(chunks),
				"chunk_size": chunk_size,
				"model": args.model,
				"dataset": os.path.basename(args.input)
			}
			with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
				json.dump(summary, f, indent=2)
			print(f"[info] Metadata saved to {out_dir}")
			
			# Log artifacts to MLflow
			mlflow.log_artifact(str(out_dir / "chunks.json"))
			mlflow.log_artifact(str(out_dir / "summary.json"))
		
		print(f"[info] MLflow run logged to {mlflow_uri}")
	
	return 0

if __name__ == "__main__":
	raise SystemExit(main())

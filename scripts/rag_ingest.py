#!/usr/bin/env python3
"""
Simple RAG ingestion pipeline with MLflow tracking
Runs: fetch → chunk → embed → validate → store
No Airflow complexity - just a straightforward Python script
"""
import os
import sys
from datetime import datetime
import requests
import pandas as pd
import mlflow
from sentence_transformers import SentenceTransformer
import psycopg2
from psycopg2.extras import Json

# Configuration
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow.mlflow.svc.cluster.local:5000')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://dosm_admin:<YOUR-DB-PASSWORD>@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-dev-postgres?sslmode=require')
DOSM_DATA_URL = "https://storage.dosm.gov.my/labour/lfs_month_duration.csv"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 25

def main():
    """Run the complete RAG ingestion pipeline"""
    run_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"🚀 RAG Ingestion Pipeline Starting - {run_date}")
    print(f"📊 MLflow URI: {MLFLOW_TRACKING_URI}")
    print(f"🗄️  Database: {DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'configured'}")
    
    # Setup MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("rag-ingestion")
    
    with mlflow.start_run(run_name=f"ingest_{run_date}"):
        print(f"🚀 Starting RAG ingestion pipeline for {run_date}")
        mlflow.log_param("run_date", run_date)
        mlflow.log_param("data_source", DOSM_DATA_URL)
        
        # Step 1: Fetch data
        print("📥 Step 1: Fetching DOSM data...")
        df = fetch_data()
        mlflow.log_metric("row_count", len(df))
        mlflow.log_metric("column_count", len(df.columns))
        print(f"   ✓ Fetched {len(df)} rows")
        
        # Step 2: Chunk data
        print(f"✂️  Step 2: Chunking data (chunk_size={CHUNK_SIZE})...")
        chunks = chunk_data(df)
        mlflow.log_param("chunk_size", CHUNK_SIZE)
        mlflow.log_metric("chunk_count", len(chunks))
        print(f"   ✓ Created {len(chunks)} chunks")
        
        # Step 3: Generate embeddings
        print("🧠 Step 3: Generating embeddings...")
        chunks_with_embeddings = generate_embeddings(chunks)
        mlflow.log_metric("embedding_count", len(chunks_with_embeddings))
        print(f"   ✓ Generated {len(chunks_with_embeddings)} embeddings")
        
        # Step 4: Validate
        print("✅ Step 4: Validating embeddings...")
        validate_embeddings(chunks_with_embeddings)
        mlflow.log_metric("validation_passed", 1)
        print("   ✓ Validation passed")
        
        # Step 5: Store in PostgreSQL
        print("💾 Step 5: Storing to PostgreSQL...")
        stored_count = store_embeddings(chunks_with_embeddings)
        mlflow.log_metric("stored_count", stored_count)
        print(f"   ✓ Stored {stored_count} embeddings")
        
        print(f"\n✨ Pipeline completed successfully!")
        print(f"   MLflow tracking: {MLFLOW_TRACKING_URI}")
        return 0

def fetch_data():
    """Fetch DOSM labour force survey data"""
    response = requests.get(DOSM_DATA_URL, timeout=30)
    response.raise_for_status()
    
    from io import StringIO
    df = pd.read_csv(StringIO(response.text))
    return df

def chunk_data(df):
    """Split dataframe into overlapping chunks"""
    chunks = []
    for i in range(0, len(df), CHUNK_SIZE):
        chunk_df = df.iloc[i:i+CHUNK_SIZE]
        chunk_text = chunk_df.to_csv(index=False, header=True)
        chunks.append({
            'text': chunk_text,
            'metadata': {
                'start_row': i,
                'end_row': min(i+CHUNK_SIZE, len(df)),
                'row_count': len(chunk_df)
            }
        })
    return chunks

def generate_embeddings(chunks):
    """Generate embeddings using sentence-transformers"""
    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [c['text'] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)
    
    for chunk, embedding in zip(chunks, embeddings):
        chunk['embedding'] = embedding.tolist()
    
    return chunks

def validate_embeddings(chunks):
    """Validate embedding quality"""
    assert len(chunks) > 0, "No chunks to validate"
    
    for chunk in chunks:
        assert 'embedding' in chunk, "Missing embedding"
        assert len(chunk['embedding']) == 384, f"Wrong embedding dimension: {len(chunk['embedding'])}"
    
    return True

def store_embeddings(chunks):
    """Store embeddings in PostgreSQL with pgvector"""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    stored_count = 0
    for chunk in chunks:
        try:
            # Generate unique ID from text hash
            chunk_id = f"chunk_{hash(chunk['text']) % 10**10}"
            
            # Insert or update embedding using the schema: id, content, embedding, metadata
            cursor.execute("""
                INSERT INTO embeddings (id, content, embedding, metadata, created_at)
                VALUES (%s, %s, %s::vector, %s, NOW())
                ON CONFLICT (id) DO UPDATE 
                SET content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    created_at = NOW()
            """, (
                chunk_id,
                chunk['text'],
                chunk['embedding'],
                Json(chunk['metadata'])
            ))
            stored_count += 1
        except Exception as e:
            print(f"⚠️  Warning: Failed to store chunk: {e}")
            conn.rollback()
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return stored_count

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

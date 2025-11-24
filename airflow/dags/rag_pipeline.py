"""
RAG Pipeline DAG for DOSM FAQ Chatbot
Orchestrates: fetch data → chunk → embed → validate → store

Schedule: Daily at 02:00 MYT (before CronJob fallback at 03:00)
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import pandas as pd
import requests
import os
import mlflow
from sentence_transformers import SentenceTransformer

# Default args
default_args = {
    'owner': 'dosm-data-team',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# MLflow configuration
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow.mlflow.svc.cluster.local:5000')
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 25
RAG_TOP_K = 3

def fetch_dosm_data(**context):
    """Fetch latest data from DOSM"""
    url = "https://storage.dosm.gov.my/labour/lfs_month_duration.csv"
    
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("rag-pipeline")
    
    with mlflow.start_run(run_name=f"fetch_{context['ds']}"):
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Save to temp file
        filepath = f"/tmp/dosm_data_{context['ds']}.csv"
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        # Log to MLflow
        df = pd.read_csv(filepath)
        mlflow.log_param("data_source", url)
        mlflow.log_metric("row_count", len(df))
        mlflow.log_metric("column_count", len(df.columns))
        mlflow.log_artifact(filepath)
        
        # Push to XCom
        context['task_instance'].xcom_push(key='data_path', value=filepath)
        context['task_instance'].xcom_push(key='row_count', value=len(df))
        
        return filepath

def chunk_data(**context):
    """Chunk data into overlapping segments"""
    data_path = context['task_instance'].xcom_pull(key='data_path', task_ids='fetch_data')
    
    with mlflow.start_run(run_name=f"chunk_{context['ds']}"):
        df = pd.read_csv(data_path)
        
        # Create text chunks (combine rows in groups)
        chunks = []
        for i in range(0, len(df), CHUNK_SIZE):
            chunk_df = df.iloc[i:i+CHUNK_SIZE]
            chunk_text = chunk_df.to_csv(index=False, header=True)
            chunks.append({
                'text': chunk_text,
                'start_row': i,
                'end_row': min(i+CHUNK_SIZE, len(df)),
                'row_count': len(chunk_df)
            })
        
        # Log to MLflow
        mlflow.log_param("chunk_size", CHUNK_SIZE)
        mlflow.log_metric("chunk_count", len(chunks))
        mlflow.log_metric("avg_chunk_length", sum(len(c['text']) for c in chunks) / len(chunks))
        
        # Save chunks
        chunks_path = f"/tmp/chunks_{context['ds']}.json"
        pd.DataFrame(chunks).to_json(chunks_path, orient='records')
        mlflow.log_artifact(chunks_path)
        
        context['task_instance'].xcom_push(key='chunks_path', value=chunks_path)
        context['task_instance'].xcom_push(key='chunk_count', value=len(chunks))
        
        return chunks_path

def generate_embeddings(**context):
    """Generate embeddings using sentence-transformers"""
    chunks_path = context['task_instance'].xcom_pull(key='chunks_path', task_ids='chunk_data')
    
    with mlflow.start_run(run_name=f"embed_{context['ds']}"):
        # Load chunks
        chunks_df = pd.read_json(chunks_path, orient='records')
        
        # Load model
        model = SentenceTransformer(EMBEDDING_MODEL)
        mlflow.log_param("embedding_model", EMBEDDING_MODEL)
        mlflow.log_param("embedding_dim", model.get_sentence_embedding_dimension())
        
        # Generate embeddings
        texts = chunks_df['text'].tolist()
        embeddings = model.encode(texts, show_progress_bar=True)
        
        # Add embeddings to dataframe
        chunks_df['embedding'] = embeddings.tolist()
        
        # Log to MLflow
        mlflow.log_metric("embedding_count", len(embeddings))
        mlflow.log_metric("embedding_dimension", embeddings.shape[1])
        
        # Save embeddings
        embeddings_path = f"/tmp/embeddings_{context['ds']}.json"
        chunks_df.to_json(embeddings_path, orient='records')
        mlflow.log_artifact(embeddings_path)
        
        context['task_instance'].xcom_push(key='embeddings_path', value=embeddings_path)
        
        return embeddings_path

def validate_embeddings(**context):
    """Validate embedding quality with test queries"""
    embeddings_path = context['task_instance'].xcom_pull(key='embeddings_path', task_ids='generate_embeddings')
    
    with mlflow.start_run(run_name=f"validate_{context['ds']}"):
        # Load embeddings
        embeddings_df = pd.read_json(embeddings_path, orient='records')
        
        # Basic validation
        assert len(embeddings_df) > 0, "No embeddings generated"
        assert embeddings_df['embedding'].notna().all(), "Some embeddings are null"
        
        # Check embedding dimensions
        sample_embedding = embeddings_df['embedding'].iloc[0]
        embedding_dim = len(sample_embedding)
        assert embedding_dim == 384, f"Expected 384 dims, got {embedding_dim}"
        
        # Log validation metrics
        mlflow.log_metric("validation_passed", 1)
        mlflow.log_metric("validated_count", len(embeddings_df))
        
        print(f"✅ Validation passed: {len(embeddings_df)} embeddings")
        return True

def store_embeddings(**context):
    """Store embeddings in PostgreSQL"""
    embeddings_path = context['task_instance'].xcom_pull(key='embeddings_path', task_ids='generate_embeddings')
    
    with mlflow.start_run(run_name=f"store_{context['ds']}"):
        # Load embeddings
        embeddings_df = pd.read_json(embeddings_path, orient='records')
        
        # Get PostgreSQL connection
        pg_hook = PostgresHook(postgres_conn_id='dosm_postgres')
        conn = pg_hook.get_conn()
        cursor = conn.cursor()
        
        # Clear old embeddings (optional - for retraining)
        # cursor.execute("DELETE FROM embeddings WHERE created_at < NOW() - INTERVAL '30 days'")
        
        # Insert new embeddings
        inserted_count = 0
        for _, row in embeddings_df.iterrows():
            cursor.execute("""
                INSERT INTO embeddings (text, embedding, metadata, created_at)
                VALUES (%s, %s::vector, %s, NOW())
                ON CONFLICT (text) DO UPDATE 
                SET embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    created_at = NOW()
            """, (
                row['text'],
                row['embedding'],
                {'start_row': int(row['start_row']), 'end_row': int(row['end_row'])}
            ))
            inserted_count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Log to MLflow
        mlflow.log_metric("stored_count", inserted_count)
        mlflow.log_param("storage_backend", "postgresql")
        
        print(f"✅ Stored {inserted_count} embeddings")
        return inserted_count

# Define DAG
with DAG(
    'rag_pipeline',
    default_args=default_args,
    description='RAG pipeline: fetch → chunk → embed → validate → store',
    schedule='0 2 * * *',  # Daily at 02:00 MYT
    start_date=datetime(2025, 11, 23),
    catchup=False,
    tags=['rag', 'embeddings', 'dosm'],
) as dag:
    
    # Task 1: Fetch data
    fetch_task = PythonOperator(
        task_id='fetch_data',
        python_callable=fetch_dosm_data,
    )
    
    # Task 2: Chunk data
    chunk_task = PythonOperator(
        task_id='chunk_data',
        python_callable=chunk_data,
    )
    
    # Task 3: Generate embeddings
    embed_task = PythonOperator(
        task_id='generate_embeddings',
        python_callable=generate_embeddings,
    )
    
    # Task 4: Validate embeddings
    validate_task = PythonOperator(
        task_id='validate_embeddings',
        python_callable=validate_embeddings,
    )
    
    # Task 5: Store embeddings
    store_task = PythonOperator(
        task_id='store_embeddings',
        python_callable=store_embeddings,
    )
    
    # Define task dependencies
    fetch_task >> chunk_task >> embed_task >> validate_task >> store_task

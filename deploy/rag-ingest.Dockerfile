# Simple RAG ingestion container - No Airflow bloat
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    requests==2.31.0 \
    pandas==2.0.3 \
    mlflow==2.9.2 \
    sentence-transformers==3.0.1 \
    psycopg2-binary==2.9.9

# Copy script
COPY scripts/rag_ingest.py /app/rag_ingest.py
RUN chmod +x /app/rag_ingest.py

# Run as non-root
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

ENTRYPOINT ["python", "/app/rag_ingest.py"]

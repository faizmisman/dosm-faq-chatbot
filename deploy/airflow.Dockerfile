# Custom Airflow image with ML pipeline dependencies
FROM apache/airflow:3.0.2

# Install required Python packages for RAG pipeline
USER airflow
RUN pip install --no-cache-dir \
    apache-airflow-providers-postgres==5.12.0 \
    sentence-transformers==2.2.2 \
    mlflow==2.9.2 \
    pandas==2.0.3 \
    psycopg2-binary==2.9.9

USER root
# Any system packages if needed
# RUN apt-get update && apt-get install -y <packages>

USER airflow

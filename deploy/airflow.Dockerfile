# Custom Airflow image with ML pipeline dependencies
FROM apache/airflow:3.0.2

# Switch to root to install system dependencies
USER root
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Switch back to airflow user to install Python packages
USER airflow
RUN pip install --no-cache-dir \
    apache-airflow-providers-postgres==5.12.0 \
    sentence-transformers==3.0.1 \
    mlflow==2.9.2 \
    pandas==2.0.3 \
    psycopg2-binary==2.9.9

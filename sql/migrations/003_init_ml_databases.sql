-- Create databases for ML pipeline components
-- Execute with: psql -h <host> -U <user> -d postgres -f 003_init_ml_databases.sql

-- Create Airflow metadata database
create database airflow_metadata;

-- Create MLflow tracking database
create database mlflow_tracking;

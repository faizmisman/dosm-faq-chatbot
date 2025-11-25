#!/bin/bash
set -e

echo "Creating airflow_metadata database..."
kubectl run create-airflow-db --rm -i --image=postgres:15 --restart=Never -- \
  psql "postgresql://dosm_admin:<URL-ENCODED-PASSWORD>@pg-dosm.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -c "CREATE DATABASE airflow_metadata;" || echo "Database may already exist"

echo "Creating mlflow_tracking database..."
kubectl run create-mlflow-db --rm -i --image=postgres:15 --restart=Never -- \
  psql "postgresql://dosm_admin:<URL-ENCODED-PASSWORD>@pg-dosm.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -c "CREATE DATABASE mlflow_tracking;" || echo "Database may already exist"

echo "Done!"

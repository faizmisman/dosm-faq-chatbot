"""
Simple Test DAG for Airflow + MLflow Integration
Tests basic Python operators and MLflow tracking
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import mlflow

# MLflow configuration
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow.mlflow.svc.cluster.local:5000')

def test_task_1(**context):
    """Test task with MLflow logging"""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("test-pipeline")
    
    with mlflow.start_run(run_name=f"test_1_{context['ds']}"):
        # Log some test metrics
        mlflow.log_param("task", "test_task_1")
        mlflow.log_param("execution_date", context['ds'])
        mlflow.log_metric("test_value", 42)
        
        print(f"✅ Test task 1 completed: {context['ds']}")
        return {"status": "success", "value": 42}

def test_task_2(**context):
    """Another test task"""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("test-pipeline")
    
    with mlflow.start_run(run_name=f"test_2_{context['ds']}"):
        mlflow.log_param("task", "test_task_2")
        mlflow.log_metric("test_value", 100)
        
        print(f"✅ Test task 2 completed: {context['ds']}")
        return {"status": "success", "value": 100}

# DAG definition
with DAG(
    'test_pipeline',
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=1),
    },
    description='Simple test DAG for Airflow + MLflow',
    schedule=None,  # Manual trigger only
    start_date=datetime(2025, 11, 24),
    catchup=False,
    tags=['test', 'mlflow'],
) as dag:
    
    task1 = PythonOperator(
        task_id='test_task_1',
        python_callable=test_task_1,
    )
    
    task2 = PythonOperator(
        task_id='test_task_2',
        python_callable=test_task_2,
    )
    
    task1 >> task2

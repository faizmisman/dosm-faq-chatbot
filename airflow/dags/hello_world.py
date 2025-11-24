"""
Minimal Test DAG - No external dependencies
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

def hello_world(**context):
    """Simple hello world task"""
    print(f"✅ Hello from Airflow! Execution date: {context['ds']}")
    return {"status": "success", "message": "Hello World"}

def goodbye_world(**context):
    """Simple goodbye task"""
    print(f"✅ Goodbye from Airflow! Execution date: {context['ds']}")
    return {"status": "success", "message": "Goodbye World"}

# DAG definition
with DAG(
    'hello_world',
    default_args={
        'owner': 'airflow',
        'retries': 1,
        'retry_delay': timedelta(minutes=1),
    },
    description='Minimal test DAG',
    schedule=None,
    start_date=datetime(2025, 11, 24),
    catchup=False,
    tags=['test', 'simple'],
) as dag:
    
    hello = PythonOperator(
        task_id='hello_world',
        python_callable=hello_world,
        provide_context=True,
    )
    
    goodbye = PythonOperator(
        task_id='goodbye_world',
        python_callable=goodbye_world,
        provide_context=True,
    )
    
    hello >> goodbye

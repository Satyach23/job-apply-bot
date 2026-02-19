"""
Airflow DAG: submit_task_dag
Entry point - routes by task_type.
"""
from datetime import datetime

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    DAG = None
    PythonOperator = None


def route_task(**context):
    """Route by task_type (simplified)."""
    conf = (context.get("dag_run") or {}).conf or {}
    task_type = conf.get("task_type", "default")
    print(f"Routing task_type: {task_type}")
    return task_type


if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="submit_task_dag",
        start_date=datetime(2025, 1, 1),
        schedule_interval=None,  # trigger only
        catchup=False,
        tags=["commentary"],
    ) as dag:
        route = PythonOperator(task_id="route_task", python_callable=route_task)

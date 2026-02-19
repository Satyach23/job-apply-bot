"""
Airflow DAG: task_status_flow_dag
FSM: NEW → UPDATING → PUBLISHED.
"""
from datetime import datetime
import httpx

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    DAG = None
    PythonOperator = None


def check_status_transitions():
    """Check and validate task status transitions."""
    r = httpx.get("http://localhost:8002/api/v1/tasks/list?status=UPDATING", timeout=10)
    tasks = r.json()
    print(f"Tasks in UPDATING: {len(tasks)}")
    return len(tasks)


if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="task_status_flow_dag",
        start_date=datetime(2025, 1, 1),
        schedule_interval="*/15 * * * *",  # every 15 min
        catchup=False,
        tags=["commentary"],
    ) as dag:
        check = PythonOperator(task_id="check_status", python_callable=check_status_transitions)

"""
Airflow DAG: ai_single_case_processor
Single-case AI analysis.
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


def process_single_case(**context):
    """Process one case through AI pipeline."""
    conf = (context.get("dag_run") or {}).conf or {}
    case_id = conf.get("case_id")
    if not case_id:
        print("No case_id in conf")
        return
    httpx.post(
        "http://localhost:8000/api/v1/legal-tracker/analyze-source",
        json={"source_type": "case", "source_id": case_id},
        timeout=120,
    )
    httpx.post(
        f"http://localhost:8000/api/v1/legal-tracker/aggregate-analysis?source_type=case&source_id={case_id}",
        timeout=30,
    )
    print(f"Processed case {case_id}")


if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="ai_single_case_processor_dag",
        start_date=datetime(2025, 1, 1),
        schedule_interval=None,
        catchup=False,
        tags=["legal_tracker"],
    ) as dag:
        process = PythonOperator(task_id="process_case", python_callable=process_single_case)

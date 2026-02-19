"""
Airflow DAG: lt_ingestion_case_process_dag
Case processing pipeline - ingest cases and trigger AI analysis.
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


def get_pending_cases():
    """Get cases that passed P0 but not yet analyzed."""
    r = httpx.get("http://localhost:8001/api/v1/case_bundle/list", timeout=10)
    cases = r.json()
    return [c for c in cases if c.get("passed_p0")]


def analyze_case(case_id: int):
    """Trigger schedule_svc analyze-source for a case."""
    httpx.post(
        "http://localhost:8000/api/v1/legal-tracker/analyze-source",
        json={"source_type": "case", "source_id": case_id},
        timeout=120,
    )
    httpx.post(
        f"http://localhost:8000/api/v1/legal-tracker/aggregate-analysis?source_type=case&source_id={case_id}",
        timeout=30,
    )


def process_cases(**context):
    ti = context.get("ti")
    cases = context.get("cases", [])
    for c in cases:
        analyze_case(c["id"])


def get_cases_and_process(**context):
    cases = get_pending_cases()
    for c in cases:
        analyze_case(c["id"])
    return len(cases)


if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="lt_ingestion_case_process_dag",
        start_date=datetime(2025, 1, 1),
        schedule_interval="*/30 * * * *",  # every 30 min
        catchup=False,
        tags=["legal_tracker"],
    ) as dag:
        process = PythonOperator(task_id="process_cases", python_callable=get_cases_and_process)

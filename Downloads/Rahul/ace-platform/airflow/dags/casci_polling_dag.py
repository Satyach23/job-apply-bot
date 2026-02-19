"""
Airflow DAG: casci_polling_dag
Polls CASCI for new case/legislation assignments.
"""
from datetime import datetime
import httpx

# Airflow imports (when run in Airflow)
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    DAG = None
    PythonOperator = None


def poll_casci():
    """Poll CASCI mock for assignments."""
    try:
        r = httpx.get("http://localhost:8200/mock/casci/poll", timeout=10)
        data = r.json()
        print(f"CASCI assignments: {data.get('count', 0)}")
        return data
    except Exception as e:
        print(f"CASCI poll failed: {e}")
        return {"assignments": [], "count": 0}


def trigger_ingestion(**context):
    """Trigger data_injection_svc for each assignment."""
    ti = context.get("ti")
    data = ti.xcom_pull(task_ids="poll_casci")
    assignments = data.get("assignments", [])
    for a in assignments:
        if "case_name" in a:
            httpx.post(
                "http://localhost:8001/api/v1/case_bundle/ingest",
                json={"case_name": a["case_name"], "court": a.get("court", "US Court of Appeals"), "citation": a.get("citation")},
                timeout=10,
            )
        elif "title" in a:
            httpx.post(
                "http://localhost:8001/api/v1/legislation_bundle/ingest",
                json={"title": a["title"], "effect_type": a.get("effect_type", "amended")},
                timeout=10,
            )


if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="casci_polling_dag",
        start_date=datetime(2025, 1, 1),
        schedule_interval="0 * * * *",  # hourly
        catchup=False,
        tags=["legal_tracker"],
    ) as dag:
        poll = PythonOperator(task_id="poll_casci", python_callable=poll_casci)
        ingest = PythonOperator(task_id="trigger_ingestion", python_callable=trigger_ingestion)
        poll >> ingest

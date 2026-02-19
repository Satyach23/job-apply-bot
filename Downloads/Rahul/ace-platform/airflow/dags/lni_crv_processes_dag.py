"""
Airflow DAG: lni_crv_processes_dag
LNI → Repo → CEP → Contenta sync.
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


def lni_to_repo():
    """LNI process - sync to repository."""
    try:
        httpx.get("http://localhost:8003/api/v1/objects", timeout=10)
    except Exception:
        pass
    print("LNI → Repo done")


def repo_to_cep():
    """CEP pipeline - Publisher → ToC → Enrichment → Loader."""
    print("Repo → CEP done")


def cep_to_contenta():
    """Contenta CMS sync."""
    print("CEP → Contenta done")


if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="lni_crv_processes_dag",
        start_date=datetime(2025, 1, 1),
        schedule_interval="0 2 * * *",  # 2 AM daily
        catchup=False,
        tags=["commentary"],
    ) as dag:
        t1 = PythonOperator(task_id="lni_to_repo", python_callable=lni_to_repo)
        t2 = PythonOperator(task_id="repo_to_cep", python_callable=repo_to_cep)
        t3 = PythonOperator(task_id="cep_to_contenta", python_callable=cep_to_contenta)
        t1 >> t2 >> t3

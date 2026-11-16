import os

from prefect import flow
from prefect.client.schemas.schedules import CronSchedule
from prefect.logging import get_run_logger

from dataops.run import run_pipeline


@flow(name="daily-velib-data-pipeline", log_prints=True)
def daily_pipeline() -> int:
    logger = get_run_logger()
    try:
        count = run_pipeline()
        logger.info("Pipeline completed for %s stations", count)
        return count
    except Exception:
        _notify_failure(logger)
        raise


def _notify_failure(logger) -> None:
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        logger.error("Pipeline failed; configure ALERT_WEBHOOK_URL to send an external alert.")
        return

    import requests

    try:
        response = requests.post(
            webhook_url,
            json={"text": "DataOps Vélib': l'exécution quotidienne du pipeline a échoué."},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Pipeline failed and the alert webhook could not be reached.")


def main() -> None:
    daily_pipeline()
    daily_pipeline.serve(
        name="daily-velib",
        schedules=[
            CronSchedule(
                cron=os.getenv("SCHEDULE_CRON", "0 6 * * *"),
                timezone="UTC",
            )
        ],
        pause_on_shutdown=False,
    )


if __name__ == "__main__":
    main()

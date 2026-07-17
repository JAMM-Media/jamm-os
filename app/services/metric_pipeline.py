# app/services/metric_pipeline.py

"""
Nightly metric aggregation pipeline. Orchestrates compute_metric() (see
app/services/metric_compute.py) across every active metric_registry row,
with per-metric isolation so one metric's failure never blocks the others.
"""

import logging
from datetime import datetime, timezone

from app.core.enums import MetricRunStatus
from app.db.session import SessionLocal
from app.models.metric_registry import MetricRegistry
from app.models.metric_run_log import MetricRunLog
from app.services.metric_compute import compute_metric

log = logging.getLogger(__name__)


def run_nightly_metric_recompute() -> dict:
    db = SessionLocal()
    try:
        run_log = MetricRunLog(
            started_at=datetime.now(timezone.utc),
            status=MetricRunStatus.running,
        )
        db.add(run_log)
        db.commit()
        db.refresh(run_log)

        computed_at = datetime.now(timezone.utc)
        active_metrics = (
            db.query(MetricRegistry)
            .filter(MetricRegistry.is_active == True)
            .order_by(MetricRegistry.key)
            .all()
        )

        succeeded = 0
        failures: list[str] = []

        for metric_row in active_metrics:
            try:
                compute_metric(db, metric_row, computed_at)
                db.commit()
                succeeded += 1
            except Exception as exc:
                db.rollback()
                failures.append(f"{metric_row.key}: {type(exc).__name__}: {exc}")
                log.error(
                    "run_nightly_metric_recompute: metric %s failed: %s",
                    metric_row.key, exc, exc_info=True,
                )

        total = len(active_metrics)
        if total == 0:
            run_log.status = MetricRunStatus.succeeded
            run_log.error_summary = "no active metrics found"
        elif not failures:
            run_log.status = MetricRunStatus.succeeded
            run_log.error_summary = None
        elif succeeded == 0:
            run_log.status = MetricRunStatus.failed
            run_log.error_summary = f"0/{total} succeeded; failed: " + "; ".join(failures)
        else:
            run_log.status = MetricRunStatus.partial
            run_log.error_summary = f"{succeeded}/{total} succeeded; failed: " + "; ".join(failures)

        run_log.finished_at = datetime.now(timezone.utc)
        db.commit()

        log.info(
            "run_nightly_metric_recompute: status=%s succeeded=%s/%s",
            run_log.status.value, succeeded, total,
        )
        return {
            "status": run_log.status.value,
            "succeeded": succeeded,
            "total": total,
            "error_summary": run_log.error_summary,
        }

    except Exception as exc:
        db.rollback()
        crash_summary = f"run crashed: {type(exc).__name__}: {exc}"
        log.error("run_nightly_metric_recompute: run crashed: %s", exc, exc_info=True)
        try:
            run_log.status = MetricRunStatus.failed
            run_log.error_summary = crash_summary
            run_log.finished_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
            log.error("run_nightly_metric_recompute: failed to record crash on run_log", exc_info=True)
        return {
            "status": MetricRunStatus.failed.value,
            "succeeded": 0,
            "total": 0,
            "error_summary": crash_summary,
        }

    finally:
        db.close()

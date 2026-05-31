# app/core/scheduler_lock.py

"""
Process lock for APScheduler.

When Gunicorn runs multiple worker processes, each worker runs
FastAPI's lifespan() independently. Without a lock, every worker
starts its own BackgroundScheduler and every job fires N times
(once per worker).

On Linux/macOS: uses fcntl.flock() on a file lock so only one
worker process starts the scheduler.

On Windows (dev): fcntl is not available, so a simple always-acquire
stub is used. Single-process dev servers are assumed.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

_lock_fh = None


if sys.platform == "win32":
    def try_acquire_scheduler_lock() -> bool:
        logger.info("Scheduler lock acquired (Windows stub) PID %s", os.getpid())
        return True

    def release_scheduler_lock() -> None:
        pass

else:
    import fcntl

    _LOCK_FILE_PATH = "/tmp/jammpx_scheduler.lock"

    def try_acquire_scheduler_lock() -> bool:
        global _lock_fh
        try:
            _lock_fh = open(_LOCK_FILE_PATH, "w")
            fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_fh.write(str(os.getpid()))
            _lock_fh.flush()
            logger.info(
                "Scheduler lock acquired by PID %s -- this worker will run scheduled jobs",
                os.getpid(),
            )
            return True
        except BlockingIOError:
            if _lock_fh:
                _lock_fh.close()
                _lock_fh = None
            logger.info(
                "Scheduler lock NOT acquired by PID %s -- another worker is running scheduled jobs",
                os.getpid(),
            )
            return False

    def release_scheduler_lock() -> None:
        global _lock_fh
        if _lock_fh:
            try:
                fcntl.flock(_lock_fh, fcntl.LOCK_UN)
                _lock_fh.close()
            except Exception:
                pass
            finally:
                _lock_fh = None

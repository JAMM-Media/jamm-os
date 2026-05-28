# app/core/scheduler_lock.py

"""
Process lock for APScheduler.

When Gunicorn runs multiple worker processes, each worker runs
FastAPI's lifespan() independently. Without a lock, every worker
starts its own BackgroundScheduler and every job fires N times
(once per worker).

This module uses a file lock (/tmp/jammpx_scheduler.lock) with
fcntl.flock() to ensure only one worker process starts the
scheduler. The lock is held for the lifetime of the process.
If the lock-holding worker dies, the OS releases the lock and
the next worker to acquire it takes over scheduling.

fcntl is Unix-only — this works on the DigitalOcean droplet.
"""

import logging
import os
import sys
if sys.platform != "win32":
    import fcntl

logger = logging.getLogger(__name__)

_LOCK_FILE_PATH = "/tmp/jammpx_scheduler.lock"
_lock_fh = None  # module-level handle — keeps the file open so the lock is held


def try_acquire_scheduler_lock() -> bool:
    """
    Try to acquire the scheduler lock.

    Returns True if this process acquired the lock and should start
    the scheduler. Returns False if another process already holds
    the lock — this worker should skip scheduler startup.

    The lock is held until the process exits (or release_scheduler_lock
    is called). The OS releases it automatically on process death.
    """
    global _lock_fh

    try:
        _lock_fh = open(_LOCK_FILE_PATH, "w")
        if sys.platform != "win32":
            fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fh.write(str(os.getpid()))
        _lock_fh.flush()
        logger.info(
            "Scheduler lock acquired by PID %s — this worker will run scheduled jobs",
            os.getpid(),
        )
        return True
    except BlockingIOError:
        # Another worker holds the lock
        if _lock_fh:
            _lock_fh.close()
            _lock_fh = None
        logger.info(
            "Scheduler lock NOT acquired by PID %s — another worker is running scheduled jobs",
            os.getpid(),
        )
        return False


def release_scheduler_lock() -> None:
    """
    Release the scheduler lock on shutdown.
    Called during lifespan cleanup (the finally block).
    """
    global _lock_fh
    if _lock_fh:
        try:
            if sys.platform != "win32":
                fcntl.flock(_lock_fh, fcntl.LOCK_UN)
            _lock_fh.close()
        except Exception:
            pass
        finally:
            _lock_fh = None

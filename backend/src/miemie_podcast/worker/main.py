from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import socket
import time
from typing import Optional

from miemie_podcast.application.container import get_container
from miemie_podcast.config import settings
from miemie_podcast.worker.runner import WorkerRunner


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def build_worker_id(slot: int, pid: Optional[int] = None, hostname: Optional[str] = None) -> str:
    resolved_pid = pid if pid is not None else os.getpid()
    resolved_hostname = hostname or socket.gethostname()
    return f"worker-{resolved_hostname}-{slot:02d}-{resolved_pid}"


def run_worker_loop(slot: int) -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    container = get_container()
    runner = WorkerRunner(container)
    worker_id = build_worker_id(slot)
    logger.info(
        "Worker started: slot=%s, worker_id=%s, poll_interval_seconds=%s",
        slot,
        worker_id,
        settings.worker_poll_interval_seconds,
    )
    while True:
        processed = runner.run_once(worker_id)
        if processed == 0:
            time.sleep(settings.worker_poll_interval_seconds)


def _start_worker_process(slot: int) -> multiprocessing.Process:
    process = multiprocessing.Process(
        target=run_worker_loop,
        args=(slot,),
        name=f"miemie-worker-{slot}",
    )
    process.start()
    return process


def supervise_workers(process_count: int) -> None:
    logger = logging.getLogger(__name__)
    shutdown_requested = False

    def handle_shutdown(signum, _frame) -> None:
        nonlocal shutdown_requested
        logger.info("Worker supervisor received signal=%s, stopping child workers.", signum)
        shutdown_requested = True

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    processes = {slot: _start_worker_process(slot) for slot in range(1, process_count + 1)}
    logger.info("Worker supervisor started %s child process(es).", len(processes))
    try:
        while not shutdown_requested:
            for slot, process in list(processes.items()):
                if process.is_alive():
                    continue
                logger.warning(
                    "Worker child exited unexpectedly: slot=%s pid=%s exitcode=%s. Restarting.",
                    slot,
                    process.pid,
                    process.exitcode,
                )
                replacement = _start_worker_process(slot)
                processes[slot] = replacement
                logger.info("Worker child restarted: slot=%s pid=%s", slot, replacement.pid)
            time.sleep(1)
    finally:
        for process in processes.values():
            if process.is_alive():
                process.terminate()
        for process in processes.values():
            process.join(timeout=5)


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    if settings.worker_process_count == 1:
        logger.info("Worker running in single-process mode.")
        run_worker_loop(1)
        return
    logger.info("Worker supervisor starting with process_count=%s", settings.worker_process_count)
    supervise_workers(settings.worker_process_count)


if __name__ == "__main__":
    main()

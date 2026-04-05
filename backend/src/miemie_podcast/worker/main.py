from __future__ import annotations

import logging
import time

from miemie_podcast.application.container import get_container
from miemie_podcast.config import settings
from miemie_podcast.worker.runner import WorkerRunner


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    container = get_container()
    runner = WorkerRunner(container)
    worker_id = "worker-default"
    logger.info(
        "Worker started: worker_id=%s, poll_interval_seconds=%s",
        worker_id,
        settings.worker_poll_interval_seconds,
    )
    while True:
        processed = runner.run_once(worker_id)
        if processed == 0:
            time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()

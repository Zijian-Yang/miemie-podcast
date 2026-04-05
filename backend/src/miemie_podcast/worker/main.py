from __future__ import annotations

import time

from miemie_podcast.application.container import get_container
from miemie_podcast.config import settings
from miemie_podcast.worker.runner import WorkerRunner


def main() -> None:
    container = get_container()
    runner = WorkerRunner(container)
    worker_id = "worker-default"
    while True:
        processed = runner.run_once(worker_id)
        if processed == 0:
            time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()


from types import SimpleNamespace

from miemie_podcast.worker import main as worker_main


def test_build_worker_id_includes_hostname_slot_and_pid():
    worker_id = worker_main.build_worker_id(slot=3, pid=456, hostname="test-host")

    assert worker_id == "worker-test-host-03-456"


def test_main_uses_single_process_mode_when_configured(monkeypatch):
    calls = []
    monkeypatch.setattr(worker_main, "configure_logging", lambda: None)
    monkeypatch.setattr(worker_main, "settings", SimpleNamespace(worker_process_count=1))
    monkeypatch.setattr(worker_main, "run_worker_loop", lambda slot: calls.append(("run", slot)))
    monkeypatch.setattr(worker_main, "supervise_workers", lambda process_count: calls.append(("supervise", process_count)))

    worker_main.main()

    assert calls == [("run", 1)]


def test_main_uses_supervisor_mode_when_multiple_processes_are_configured(monkeypatch):
    calls = []
    monkeypatch.setattr(worker_main, "configure_logging", lambda: None)
    monkeypatch.setattr(worker_main, "settings", SimpleNamespace(worker_process_count=3))
    monkeypatch.setattr(worker_main, "run_worker_loop", lambda slot: calls.append(("run", slot)))
    monkeypatch.setattr(worker_main, "supervise_workers", lambda process_count: calls.append(("supervise", process_count)))

    worker_main.main()

    assert calls == [("supervise", 3)]

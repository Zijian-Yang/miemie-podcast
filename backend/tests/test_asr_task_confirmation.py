from types import SimpleNamespace

import pytest

from miemie_podcast.adapters.providers.qwen import (
    normalize_asr_task_status,
    normalize_transcription_result_url,
)
from miemie_podcast.application import services
from miemie_podcast.application.services import EpisodeService


class StubSpeechToTextProvider:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def get_result(self, task_id: str):
        self.calls += 1
        if not self.results:
            raise AssertionError("No stubbed results left.")
        return self.results.pop(0)


def make_service(results):
    service = EpisodeService.__new__(EpisodeService)
    service.settings = SimpleNamespace(worker_poll_interval_seconds=5)
    service.stt_provider = StubSpeechToTextProvider(results)
    return service


def test_normalize_asr_task_status_defaults_to_unknown():
    assert normalize_asr_task_status(None) == "UNKNOWN"
    assert normalize_asr_task_status("running") == "RUNNING"


def test_normalize_transcription_result_url_upgrades_http():
    assert normalize_transcription_result_url("http://example.com/a.json") == "https://example.com/a.json"
    assert normalize_transcription_result_url("https://example.com/a.json") == "https://example.com/a.json"


def test_confirm_transcription_task_started_retries_until_running(monkeypatch):
    monkeypatch.setattr(services.time, "sleep", lambda _: None)
    service = make_service(
        [
            {"status": "UNKNOWN", "task_id": "task_1"},
            {"status": "RUNNING", "task_id": "task_1"},
        ]
    )

    result = service._confirm_transcription_task_started("task_1")

    assert result["status"] == "RUNNING"
    assert service.stt_provider.calls == 2


def test_confirm_transcription_task_started_raises_when_not_confirmed(monkeypatch):
    monkeypatch.setattr(services.time, "sleep", lambda _: None)
    service = make_service(
        [
            {"status": "UNKNOWN", "task_id": "task_1"},
            {"status": "UNKNOWN", "task_id": "task_1"},
            {"status": "UNKNOWN", "task_id": "task_1"},
        ]
    )

    with pytest.raises(RuntimeError):
        service._confirm_transcription_task_started("task_1")

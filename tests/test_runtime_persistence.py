from pathlib import Path
import types


def test_runtime_artifact_store_writes_snapshot_and_events(fresh_import, tmp_path):
    models = fresh_import("core.runtime.models")
    persistence = fresh_import("core.runtime.persistence")
    store = persistence.RuntimeArtifactStore(tmp_path / "runtime.json")
    snapshot = models.OutputSessionSnapshot(
        request=types.SimpleNamespace(mode="screen"),
        mode=models.OutputMode.RECORD_AND_STREAM,
        stream_settings=models.StreamSettings(enabled=True, server_url="rtmp://localhost/live", stream_key="abc"),
        record_to_file=True,
    )
    session = models.OutputSession(
        mode=models.OutputMode.RECORD_AND_STREAM,
        record_path="out.mp4",
        bridge_url="udp://127.0.0.1:20000",
        stream_state=models.StreamState.RECONNECTING,
        stream_url="rtmp://localhost/live/abc",
        reconnect_attempts=2,
        reconnect_backoff_seconds=5.0,
        last_error="stream lost",
        software_fallback_active=True,
    )
    events = (
        models.RuntimeEvent(models.RuntimeEventType.STREAM_CONNECT_FAILED, "stream lost"),
    )

    store.save(snapshot, session, events)
    payload = store.load()

    assert payload["session"]["mode"] == "record_and_stream"
    assert payload["session"]["software_fallback_active"] is True
    assert payload["diagnostics"][0]["event_type"] == "stream_connect_failed"


def test_runtime_artifact_store_clear_removes_file(fresh_import, tmp_path):
    persistence = fresh_import("core.runtime.persistence")
    store = persistence.RuntimeArtifactStore(tmp_path / "runtime.json")
    Path(store.path).write_text("{}", encoding="utf-8")

    store.clear()

    assert store.exists() is False

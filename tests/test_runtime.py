import types


class RecorderStub:
    def __init__(self):
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "StreamState", "OutputSessionSnapshot"])
        self.state = None
        self.start_calls = []
        self.stop_calls = 0
        self.pause_calls = 0
        self.resume_calls = 0
        self.start_result = "out.mp4"
        self.enable_stream_calls = []
        self.disable_stream_calls = 0
        self.output_session = runtime_models.OutputSession()
        self.snapshot = runtime_models.OutputSessionSnapshot()
        self.restore_calls = []

    def start_request(self, request, stream_settings=None, record_to_file=True):
        self.start_calls.append((request, stream_settings, record_to_file))
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "OutputSessionSnapshot"])
        self.output_session = runtime_models.OutputSession(
            mode=runtime_models.OutputMode.RECORD if record_to_file else runtime_models.OutputMode.STREAM,
            record_path="out.mp4" if record_to_file else None,
            bridge_url="udp://127.0.0.1:23000",
            stream_state=self.output_session.stream_state,
            stream_url=self.output_session.stream_url,
            reconnect_attempts=self.output_session.reconnect_attempts,
        )
        self.snapshot = runtime_models.OutputSessionSnapshot(
            request=request,
            mode=self.output_session.mode,
            stream_settings=stream_settings,
            record_to_file=record_to_file,
            software_fallback_active=False,
        )
        return self.start_result

    def stop(self):
        self.stop_calls += 1
        return {"output_path": "out.mp4"}

    def pause(self):
        self.pause_calls += 1
        return True

    def resume(self):
        self.resume_calls += 1
        return True

    def enable_stream(self, stream_settings):
        self.enable_stream_calls.append(stream_settings)
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "StreamState"])
        self.output_session = runtime_models.OutputSession(
            mode=runtime_models.OutputMode.RECORD_AND_STREAM,
            record_path="out.mp4",
            bridge_url="udp://127.0.0.1:23000",
            stream_state=runtime_models.StreamState.LIVE,
            stream_url=stream_settings.output_url(),
            reconnect_attempts=0,
        )
        return True

    def disable_stream(self):
        self.disable_stream_calls += 1
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "StreamState"])
        self.output_session = runtime_models.OutputSession(
            mode=runtime_models.OutputMode.RECORD,
            record_path="out.mp4",
            bridge_url="udp://127.0.0.1:23000",
            stream_state=runtime_models.StreamState.STOPPED,
            stream_url=None,
            reconnect_attempts=0,
        )
        return True

    def get_output_session(self):
        return self.output_session

    def snapshot_output_session(self):
        return self.snapshot

    def restore_output_session(self, snapshot, prefer_software=False):
        self.restore_calls.append((snapshot, prefer_software))
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "StreamState", "OutputSessionSnapshot"])
        self.output_session = runtime_models.OutputSession(
            mode=snapshot.mode,
            record_path="out.mp4" if snapshot.record_to_file else None,
            bridge_url="udp://127.0.0.1:23000",
            stream_state=runtime_models.StreamState.LIVE if snapshot.mode != runtime_models.OutputMode.RECORD else runtime_models.StreamState.STOPPED,
            stream_url=snapshot.stream_settings.output_url() if snapshot.stream_settings else None,
            reconnect_attempts=0,
            software_fallback_active=prefer_software,
        )
        self.snapshot = runtime_models.OutputSessionSnapshot(
            request=snapshot.request,
            mode=snapshot.mode,
            stream_settings=snapshot.stream_settings,
            record_to_file=snapshot.record_to_file,
            software_fallback_active=prefer_software,
        )
        return "restored.mp4"

    @property
    def is_recording(self):
        return True


def test_diagnostics_service_returns_expected_recovery_actions(fresh_import):
    models = fresh_import("core.runtime.models")
    diagnostics_module = fresh_import("core.runtime.diagnostics")
    service = diagnostics_module.DiagnosticsService()

    action = service.report(models.RuntimeEvent(models.RuntimeEventType.ENCODER_FAILED, "Encoder crashed"))

    assert action == models.RecoveryAction.RETRY_WITH_SOFTWARE
    assert "encoder_failed" in service.latest_summary()


def test_broadcast_orchestrator_tracks_recording_and_streaming_states(fresh_import):
    models = fresh_import("core.runtime.models")
    orchestrator_module = fresh_import("core.runtime.orchestrator")
    recorder = RecorderStub()
    recorder.state = models.RecorderState.RECORDING
    request = types.SimpleNamespace()
    stream = models.StreamSettings(enabled=True, server_url="rtmp://localhost/live", stream_key="abc")
    orchestrator = orchestrator_module.BroadcastOrchestrator(recorder)

    output = orchestrator.start_recording_and_streaming(request, stream)

    assert output == "out.mp4"
    assert orchestrator.runtime_state == models.BroadcastRuntimeState.RECORDING_AND_STREAMING
    assert recorder.start_calls[0][2] is True
    assert recorder.enable_stream_calls[0] == stream


def test_broadcast_orchestrator_handles_failed_start(fresh_import):
    models = fresh_import("core.runtime.models")
    orchestrator_module = fresh_import("core.runtime.orchestrator")
    recorder = RecorderStub()
    recorder.state = models.RecorderState.FAILED
    recorder.start_result = None
    orchestrator = orchestrator_module.BroadcastOrchestrator(recorder)

    result = orchestrator.start_recording(types.SimpleNamespace())

    assert result is None
    assert orchestrator.runtime_state == models.BroadcastRuntimeState.FAILED


def test_broadcast_orchestrator_safe_stop_on_runtime_event(fresh_import):
    models = fresh_import("core.runtime.models")
    orchestrator_module = fresh_import("core.runtime.orchestrator")
    recorder = RecorderStub()
    recorder.state = models.RecorderState.RECORDING
    orchestrator = orchestrator_module.BroadcastOrchestrator(recorder)
    orchestrator.runtime_state = models.BroadcastRuntimeState.RECORDING

    action = orchestrator.report_event(
        models.RuntimeEvent(models.RuntimeEventType.FFMPEG_EXITED_UNEXPECTEDLY, "ffmpeg exited")
    )

    assert action == models.RecoveryAction.SAFE_STOP
    assert recorder.stop_calls == 1
    assert orchestrator.runtime_state == models.BroadcastRuntimeState.FAILED


def test_broadcast_orchestrator_hot_switches_stream_during_recording(fresh_import):
    models = fresh_import("core.runtime.models")
    orchestrator_module = fresh_import("core.runtime.orchestrator")
    recorder = RecorderStub()
    recorder.state = models.RecorderState.RECORDING
    orchestrator = orchestrator_module.BroadcastOrchestrator(recorder)
    orchestrator.start_recording(types.SimpleNamespace())
    stream = models.StreamSettings(enabled=True, server_url="rtmp://localhost/live", stream_key="abc")

    enabled = orchestrator.enable_stream(stream)
    disabled = orchestrator.disable_stream()

    assert enabled is True
    assert disabled is True
    assert recorder.disable_stream_calls == 1
    assert orchestrator.runtime_state == models.BroadcastRuntimeState.RECORDING


def test_broadcast_orchestrator_restores_snapshot_with_software_fallback_on_encoder_fail(fresh_import):
    models = fresh_import("core.runtime.models")
    orchestrator_module = fresh_import("core.runtime.orchestrator")
    recorder = RecorderStub()
    recorder.state = models.RecorderState.RECORDING
    orchestrator = orchestrator_module.BroadcastOrchestrator(recorder)
    request = types.SimpleNamespace()
    stream = models.StreamSettings(enabled=True, server_url="rtmp://localhost/live", stream_key="abc")
    orchestrator.start_recording_and_streaming(request, stream)

    action = orchestrator.report_event(models.RuntimeEvent(models.RuntimeEventType.ENCODER_FAILED, "encoder lost"))

    assert action == models.RecoveryAction.RETRY_WITH_SOFTWARE
    assert recorder.restore_calls[0][1] is True
    assert orchestrator.output_session.software_fallback_active is True

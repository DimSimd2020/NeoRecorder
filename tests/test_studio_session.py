import pytest


def load_modules(fresh_import):
    return (
        fresh_import("core.studio.service"),
        fresh_import("core.studio.session"),
    )


def id_factory():
    counter = {"value": 0}

    def create():
        counter["value"] += 1
        return f"id-{counter['value']}"

    return create


def test_create_session_uses_active_scene(fresh_import):
    service_module, session_module = load_modules(fresh_import)
    project_service = service_module.StudioProjectService(id_factory=id_factory())
    project = project_service.create_project("NeoRecorder")

    session = session_module.StudioSessionService().create_session(project)

    assert session.preview_scene_id == project.active_scene_id
    assert session.program_scene_id == project.active_scene_id


def test_set_preview_scene_updates_only_preview(fresh_import):
    service_module, session_module = load_modules(fresh_import)
    project_service = service_module.StudioProjectService(id_factory=id_factory())
    project = project_service.create_project("NeoRecorder")
    project = project_service.add_scene(project, "Second")
    session_service = session_module.StudioSessionService()
    session = session_service.create_session(project)

    updated = session_service.set_preview_scene(project, session, project.scenes[1].scene_id)

    assert updated.preview_scene_id == project.scenes[1].scene_id
    assert updated.program_scene_id == project.active_scene_id


def test_take_moves_preview_to_program(fresh_import):
    service_module, session_module = load_modules(fresh_import)
    project_service = service_module.StudioProjectService(id_factory=id_factory())
    project = project_service.create_project("NeoRecorder")
    project = project_service.add_scene(project, "Second")
    session_service = session_module.StudioSessionService()
    session = session_service.create_session(project)
    session = session_service.set_preview_scene(project, session, project.scenes[1].scene_id)

    updated_project, updated_session = session_service.take(project, session)

    assert updated_project.active_scene_id == project.scenes[1].scene_id
    assert updated_session.program_scene_id == project.scenes[1].scene_id


def test_set_transition_clamps_duration(fresh_import):
    _service_module, session_module = load_modules(fresh_import)
    service = session_module.StudioSessionService()
    session = session_module.StudioSession("scene", "scene")

    updated = service.set_transition(session, session_module.TransitionKind.FADE, 10)

    assert updated.transition.kind == session_module.TransitionKind.FADE
    assert updated.transition.duration_ms == 50


def test_set_preview_scene_raises_for_missing_scene(fresh_import):
    service_module, session_module = load_modules(fresh_import)
    project_service = service_module.StudioProjectService(id_factory=id_factory())
    project = project_service.create_project("NeoRecorder")
    session = session_module.StudioSessionService().create_session(project)

    with pytest.raises(Exception):
        session_module.StudioSessionService().set_preview_scene(project, session, "missing")

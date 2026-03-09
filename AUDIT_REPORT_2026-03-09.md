# Отчет по аудиту NeoRecorder

Дата: 2026-03-09

## Объем работ

- Проведен аудит backend-логики, инфраструктурных модулей и точек интеграции.
- Добавлен полный автоматизированный тестовый контур для текущего backend-функционала.
- Выполнен прогон всего набора тестов.
- Исправлены критичные дефекты, найденные во время аудита и тестирования.

## Основные проблемы, найденные на аудите

1. Пакетный конфликт импорта:
   локальный каталог `utils/` не был оформлен как Python package, из-за чего в среде мог импортироваться сторонний пакет `utils` из `site-packages`.

2. Deadlock в hotkey-менеджере:
   `HotkeyManager.register()` вызывал `unregister()` под тем же `Lock`, что могло навсегда блокировать повторную регистрацию горячих клавиш.

3. Мутация глобальных дефолтов:
   `Settings` использовал поверхностное копирование словарей, из-за чего изменение hotkeys в runtime могло менять глобальные defaults.

4. Неконсистентные переходы состояния FFmpeg:
   при неуспешном старте записи оставались хвосты состояния;
   при неудачном resume запись могла выйти в неверное состояние;
   сегменты добавлялись до подтверждения реального старта процесса.

5. Лишний side effect в трее:
   `SystemTray.notify()` писал `debug.log` рядом с исполняемым файлом, что не относится к доменной задаче уведомления.

## Исправления бекенда

- Добавлены `__init__.py` в `core/`, `gui/`, `utils/` для стабильного импорта локальных пакетов.
- Исправлен `utils.hotkeys`:
  - заменен `Lock` на `RLock`;
  - вынесено безопасное внутреннее снятие регистрации;
  - исправлено хранение и возврат реальных hotkey-строк.
- Исправлен `config.Settings`:
  - использован `deepcopy` для defaults;
  - `all` теперь возвращает глубокую копию;
  - предотвращена мутация глобальных hotkey defaults.
- Исправлен `utils.ffmpeg_handler`:
  - добавлен cleanup после неуспешного старта;
  - сегменты сохраняются только после подтвержденного старта;
  - исправлена логика `resume()` и `toggle_pause()`;
  - в `stop_recording()` корректно сбрасывается внутреннее состояние.
- Исправлен `utils.logger`:
  - логгеры теперь кешируются по имени, а не одной глобальной переменной на весь процесс.
- Исправлен `gui.tray`:
  - удален побочный эффект с записью debug-файла;
  - уведомление теперь делает только одну вещь: вызывает notify и логирует ошибку при проблеме.

## Прогресс к OBS-level

Следующим этапом добавлен новый backend-слой `core/studio/`:

- `core/studio/models.py`
  - доменные модели `StudioProject`, `Scene`, `CaptureSource`, `Bounds`;
  - явные типы источников (`display`, `window`, `region`, `microphone`, `system_audio`).
- `core/studio/service.py`
  - создание/удаление/переименование сцен;
  - добавление/обновление/удаление источников;
  - сохранение/загрузка проекта;
  - bridge из текущего legacy UI в scene-based backend.
- `core/studio/planner.py`
  - трансляция scene-конфигурации в текущий `RecordingRequest` для существующего recorder pipeline.

Текущее GUI уже начинает использовать этот слой:

- `gui.app` теперь строит live-scene из текущего UI-состояния;
- scene переводится в `RecordingRequest`;
- `ScreenRecorder` получил `start_request()`, чтобы backend-пайплайн принимал не только legacy-набор параметров, но и явный запрос от scene planner.

Это еще не multi-scene UI и не полноценный OBS mixer, но это уже правильный архитектурный фундамент для:

- scene switching;
- multi-source composition;
- profiles/presets;
- filters/mixer/output graph поверх scene model.

Следующим шагом backend расширен до layered scene graph:

- `CaptureSource` теперь хранит:
  - `z_index` для порядка слоев;
  - `opacity` для визуального микширования;
  - `volume` и `muted` для аудио-микширования.
- `Scene` теперь умеет:
  - возвращать sources в порядке композиции;
  - отделять `primary_video_source` и `overlay_video_sources`;
  - строить `mixed_audio_sources` без muted/silent channels.
- `SceneRecordingPlanner` теперь умеет:
  - строить `SceneCompositionPlan`;
  - выделять primary layer и overlays;
  - подготавливать `AudioChannel` набор для будущего mixer/output graph.
- `StudioProjectService` теперь умеет:
  - менять z-order источника;
  - менять volume/mute/opacity;
  - включать и выключать источники без удаления.

Итог: backend уже не ограничен моделью "одна сцена = один источник видео", даже если текущий runtime recorder пока использует только primary layer для фактической записи.

## Переработка фронтенда

Главный экран приложения полностью переработан из single-column recorder UI в студийный workspace:

- новый layout в [gui/app.py](E:/Development/NeoRecorder/gui/app.py):
  - header bar;
  - scene deck;
  - sources panel;
  - large preview area;
  - transport/mode controls;
  - audio mixer sidebar;
  - inspector sidebar;
  - footer status bar.
- новые reusable UI-компоненты в [gui/widgets.py](E:/Development/NeoRecorder/gui/widgets.py):
  - `ScenePreview`;
  - `MixerStrip`;
  - обновленный `VUMeter`.
- новый presenter-слой в [gui/studio_presenter.py](E:/Development/NeoRecorder/gui/studio_presenter.py) для форматирования scene/source данных.
- обновлена общая палитра в [config.py](E:/Development/NeoRecorder/config.py) и приведено окно настроек к новому визуальному языку.

Фронтенд теперь не просто рисует кнопки записи, а отображает текущую scene-модель и позволяет:

- переключать сцены;
- видеть список источников активной сцены;
- включать/выключать источники;
- менять mute/volume у аудио-источников;
- менять opacity у video-источников;
- менять z-order источника через UI;
- видеть composition preview active scene.

## Multi-monitor, encode compatibility и notifications

Следующим этапом добавлены реальные улучшения под сценарии ближе к OBS-style desktop workflow:

- Добавлен новый модуль [utils/display_manager.py](E:/Development/NeoRecorder/utils/display_manager.py):
  - перечисление физических дисплеев через `mss`;
  - виртуальные bounds рабочего стола;
  - нормализация geometry для окон overlay/toast при отрицательных координатах.
- Расширен studio backend:
  - `CaptureSource` теперь умеет отдавать `display_index()` и `display_name()` из metadata;
  - `StudioProjectService.create_display_source()` поддерживает monitor-aware display sources;
  - `SceneRecordingPlanner` теперь может строить request для конкретного монитора через display bounds.
- Обновлен desktop UI:
  - в `gui.app` добавлен выбор дисплея;
  - screen-mode теперь синхронизируется с конкретным monitor source, а не только с абстрактным "desktop".
- Обновлены `utils.screenshot`, `utils.region_selector`, `gui.quick_overlay`:
  - скриншоты можно делать с конкретного дисплея;
  - region overlay и quick overlay теперь работают по всему virtual desktop;
  - корректно возвращаются абсолютные координаты даже при multi-monitor layout с отрицательными смещениями.
- Переработан `utils.ffmpeg_handler`:
  - выбор encoder теперь идет через compatibility policy, а не через одиночный "лучший" кодек;
  - добавлены консервативные ограничения для `QSV`/`AMF` по ширине/FPS;
  - при провале hardware start идет автоматический fallback на `libx264`;
  - `ScreenRecorder` логирует фактически выбранный encoder, а не только теоретический best-match.
- Полностью заменен toast pipeline:
  - `utils.notifications` теперь содержит testable payload/layout helpers;
  - success/info/error уведомления имеют единый формат;
  - `gui.toast` переведен в совместимый adapter поверх нового renderer.

## Runtime compositor и studio mode

Следующим слоем backend/frontend переведен ближе к реальной студийной модели OBS:

- `RecordingRequest` теперь несет не только legacy-поля, но и полный `SceneCompositionPlan`.
- `ScreenRecorder` и `utils.ffmpeg_handler` теперь принимают scene plan напрямую.
- В `utils.ffmpeg_handler` добавлен runtime compositor для layered scene:
  - primary video source и overlay sources переводятся в несколько `gdigrab` inputs;
  - собирается `filter_complex` с `overlay`;
  - opacity overlays применяется через `colorchannelmixer`;
  - layered scene теперь влияет на реальную FFmpeg-команду, а не только на preview.
- Для layered scene с filter graph сохранен audio path:
  - микрофон корректно мапится при `filter_complex`;
  - volume из scene audio-channel применяется к микрофонному input.
- Добавлен новый backend-модуль [core/studio/session.py](E:/Development/NeoRecorder/core/studio/session.py):
  - `StudioSession`;
  - `TransitionKind`;
  - `TransitionSpec`;
  - `StudioSessionService`.
- GUI в [gui/app.py](E:/Development/NeoRecorder/gui/app.py) переведен на `Preview / Program` workflow:
  - отдельный preview scene;
  - отдельный program scene;
  - `TAKE` для перевода preview в program;
  - выбор transition (`cut`, `fade`, `slide`);
  - запись теперь идет из `program scene`, а не просто из выделенной для редактирования сцены.
- Preview widgets в [gui/widgets.py](E:/Development/NeoRecorder/gui/widgets.py) доработаны:
  - корректная нормализация scene bounds;
  - поддержка отрицательных координат и virtual desktop layouts;
  - более точное отображение layered scenes в studio mode.

## Добавленные тесты

Добавлено 245 автоматических тестов:

- `tests/test_config.py`
- `tests/test_display_manager.py`
- `tests/test_logger.py`
- `tests/test_hotkeys.py`
- `tests/test_window_finder.py`
- `tests/test_audio_session_manager.py`
- `tests/test_audio_manager.py`
- `tests/test_ffmpeg_handler.py`
- `tests/test_notifications.py`
- `tests/test_quick_overlay.py`
- `tests/test_recorder.py`
- `tests/test_region_selector.py`
- `tests/test_screenshot.py`
- `tests/test_studio_models.py`
- `tests/test_studio_planner.py`
- `tests/test_studio_service.py`
- `tests/test_studio_session.py`
- `tests/test_studio_presenter.py`
- `tests/test_widgets.py`

Покрытые зоны:

- конфигурация и персистентные настройки;
- логирование;
- глобальные hotkeys;
- поиск окон;
- аудио-менеджмент и WASAPI session layer;
- FFmpeg orchestration и state machine записи;
- ScreenRecorder orchestration;
- multi-monitor discovery и virtual desktop geometry;
- создание и clipboard-copy скриншотов;
- форматирование и layout toast-notifications;
- region/quick overlay сценарии для нескольких мониторов;
- scene/source models, planner и project service.
- studio session state (`preview/program/take/transition`);
- widget-level rendering logic для multi-monitor scene preview.

## Результат прогона

Команда:

```bash
pytest -q
```

Результат:

```text
245 passed in 2.51s
```

## Остаточные риски

- GUI-поведение сейчас проверено косвенно через backend-слои и изолированные заглушки, но не через полноценные desktop E2E сценарии.
- Реальная проверка работы с живым FFmpeg, физическими аудиоустройствами, WASAPI, несколькими физическими мониторами и системным треем на разных конфигурациях Windows еще нужна.
- Для следующего этапа "уровень OBS Studio" потребуется отдельный аудит архитектуры сцены, источников, микширования, плагинности и realtime pipeline.

## Итог

Проект переведен из состояния без тестов в состояние с воспроизводимым backend test-suite.
Критичные дефекты состояния, импорта и hotkey/FFmpeg orchestration исправлены.
Текущая база готова к следующему этапу: системная доработка backend под более сложный функционал записи и управления источниками.

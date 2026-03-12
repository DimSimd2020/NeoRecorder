# Broadcast Core Report

Дата: 2026-03-12

## Что реализовано

- Явные `RecorderState`, `BroadcastRuntimeState`, `OutputMode`, `StreamState`.
- `BroadcastOrchestrator` как application-layer фасад для record/stream/recovery flows.
- `OutputSession` и `OutputSessionSnapshot`.
- RTMP streaming v1 с hot-switch stream on/off во время записи.
- Stream bridge process отделён от capture process.
- Bounded reconnect policy: `1s -> 2s -> 5s`.
- Software fallback recovery path после `encoder/output start fail`.
- Runtime artifact store:
  - [core/runtime/persistence.py](E:\Development\NeoRecorder\core\runtime\persistence.py)
  - persisted artifact file: `runtime/last_output_session.json`
- Studio domain расширен:
  - новые source kinds
  - transforms
  - visibility / lock
  - duplication
  - richer audio metadata
- UI расширен:
  - stream controls
  - scene duplication
  - source duplication
  - transform editor v1
  - richer mixer telemetry

## Что это закрывает в `obs_killer_plan.md`

### Этап 1

Практически закрыт рабочий минимум:

- явная state machine записи
- runtime diagnostics/recovery
- ownership cleanup
- encoder fallback path
- recovery artifact

### Этап 2

Частично закрыт:

- transforms v1
- scene/source duplication
- image/text/color/browser/media source types
- audio mixer upgrade v1
- streaming outputs v1

## Что ещё НЕ доведено до уровня OBS

- полноценный browser runtime
- полноценный media playback/runtime
- nested scenes
- scene collections / profiles
- полноценный render graph / GPU compositor
- production-grade reconnect strategy для всех output failure classes
- replay buffer
- post-production layer
- AI layer

## Текущее состояние качества

- Полный тестовый прогон: `280 passed`
- Runtime artifact сохраняется при recoverable/failed output scenarios.
- Preview-only sources больше не маскируются под полноценный recording runtime.

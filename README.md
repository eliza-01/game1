# game1

**M655 · Global Published Debug.** `Options → Debug / TestPlace → Enable debug / test buttons`: одна глобальная галочка `debugUi.showPublishedControls`, независимо от Place ID, устройства, владельца и ранга. Все подключённые игроки опубликованного Place (включая compiled Runtime) при ON получают server-owned authorization; OFF не запускает опубликованные debug-сервисы и блокирует debug-вызовы. Studio и отдельные Studio-only инструменты GP/AG/Buffer сохраняют прежний контракт. Перед публичным релизом выключить debug: ON предоставляет тестовые полномочия всем игрокам. Миграция прежних PC/Mobile flags — OR, Place ID удаляется; default OFF для новой конфигурации. Нативная Published-приёмка открыта. Приоритет: диагностика регрессии GPU/CPU (владелец сообщил 25 → 125 ms GPU в покое), не снижение качества. Причина пока неизвестна. См. `docs/workflows/M655_GLOBAL_PUBLISHED_DEBUG_RU.md`.

Актуальная ревизия: M654 — [Animation Playback Reliability](docs/workflows/M654_ANIMATION_PLAYBACK_RELIABILITY_RU.md), приёмка Published открыта.

Независимый Roblox-проект (основа MMO) с custom characters, server-authoritative combat, Monster/NPC, Asset Manager, системой локаций/декора, Real Estate и Studio Bridge. **Не использует Place и базы RobloxLineage.**

## С чего начать

1. **[Документация — полный индекс](docs/README Read First!.md)**: действующие документы, спецификации и исторические отчёты по доменам.
2. **[Актуальное ТЗ](docs/spec/CURRENT_PROJECT_SPEC_RU.md)**: текущие механики, ограничения, дальнейшие требования и DoD.
3. **[Действующая архитектура](docs/architecture/CURRENT_ARCHITECTURE_RU.md)** и **[остаток рефакторинга](docs/architecture/REFACTOR_ROADMAP_RU.md)**.
4. **[Процесс и проверки](docs/workflows/DEVELOPMENT_AND_VALIDATION_RU.md)** и [AGENTS.md](AGENTS.md) — правила изменений.

Исторический [Milestone 1 spec](docs/history/milestone-1/PROJECT_SPEC_MILESTONE_1_RU.md) описывает **первоначальный старт**, когда существовал только Characters; он больше не описывает текущий набор систем. Отчёты M85–M105 показывают выполненную часть декомпозиции, а не задачу повторно её выполнить.

## Локальная установка и запуск (Windows)

Хранить проект отдельно, например `E:\RobloxProjects\game1`, **не** внутри/поверх `RobloxLineage`.

```powershell
.\bootstrap.ps1
```

Канонический Place: `place\game1.rbxl`. Открой его в Roblox Studio и подключи Rojo plugin к `127.0.0.1:34882`; при необходимости запусти `./sync.ps1` из корня.

```powershell
rokit install
.\system\studio-plugin\install-rojo-plugin.ps1
.\system\studio-plugin\install.ps1
.\place\build-place.ps1
.\control-center.ps1
.\sync.ps1
```

| Локальный сервис | Default address |
| --- | --- |
| Control Center | `http://127.0.0.1:43820` |
| Host Agent | `127.0.0.1:43821` |
| Rojo | `127.0.0.1:34882` |
| Studio Bridge reserved | `127.0.0.1:43137` |

Значения — базовые настройки проекта, реальные environment overrides проверять на машине пользователя. Сцена остаётся Studio-authored; live Rojo синхронизирует код, не должен перезаписывать позиции объектов Workspace.

## Проверка изменений

```powershell
python system/verify/verify.py
python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q
python system/studio-plugin/validate_luau.py
```

Runtime behaviour Roblox Studio, публикация через Open Cloud и источники Blender проверяются **отдельно**. Успех Python-тестов не означает проверенный Play session.

**Актуальная база:** диагностический дамп `game1_diag_2026-11-28_17-27-55.zip` (M651, четыре реальных MNPC captures) + M652–M653. M653 — Character component hitbox authoring, [M653](docs/workflows/M653_CHARACTER_HITBOX_COMPONENTS_RU.md), native capture open. M652 — исправление session/asset signature compatibility, native coverage открыто; [M652](docs/workflows/M652_HITBOX_CACHE_COMPATIBILITY_RU.md). M651 — MNPC hitbox authoring, native migration открыта; [M651](docs/workflows/M651_HITBOX_ASSET_PIPELINE_RU.md). M650 — исправление near-first загрузки, код готов; [M650](docs/workflows/M650_NEAR_ASSET_LOADING_RU.md). MNPC LOD функционально принят в одиночной игре; полная многопользовательская приёмка и реальные LOD1 открыты. M646–M647 — Overhead UI Pool функционально принят владельцем; полный ресурсный A05 открыт. M648 — Character Creation Prewarm CODE_COMPLETE, нативная приёмка открыта. [M648](docs/workflows/M648_CHARACTER_ASSET_PREWARM_RU.md). M649 — контракт готовых hitboxes и ограничение времени жизни геометрии; миграция открыта. [M649](docs/workflows/M649_HITBOX_ASSET_CONTRACT_RU.md). [M646](docs/workflows/M646_OVERHEAD_UI_POOL_RU.md) · [M647](docs/workflows/M647_OVERHEAD_INTEGRATION_RU.md). [READ FIRST](docs/README%20Read%20First!.md) · [MNPC](docs/workflows/MNPC_LOD_SPEC_RU.md) · [Kanban](docs/kanban/specs/KBN-0037.md).

- [M236: Location Assets — Model/Mesh ID history and Find → Replace](docs/workflows/LOCATION_ASSETS_ID_HISTORY_TWO_PHASE_SYNC_M236_RU.md)

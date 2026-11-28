# game1

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

**Актуальная база:** диагностический дамп `game1_diag_2026-11-28_16-21-34.zip` (M645) + M646–M649. MNPC LOD функционально принят в одиночной игре; полная многопользовательская приёмка и реальные LOD1 открыты. M646–M647 — Overhead UI Pool функционально принят владельцем; полный ресурсный A05 открыт. M648 — Character Creation Prewarm CODE_COMPLETE, нативная приёмка открыта. [M648](docs/workflows/M648_CHARACTER_ASSET_PREWARM_RU.md). M649 — контракт готовых hitboxes и ограничение времени жизни геометрии; миграция открыта. [M649](docs/workflows/M649_HITBOX_ASSET_CONTRACT_RU.md). [M646](docs/workflows/M646_OVERHEAD_UI_POOL_RU.md) · [M647](docs/workflows/M647_OVERHEAD_INTEGRATION_RU.md). [READ FIRST](docs/README%20Read%20First!.md) · [MNPC](docs/workflows/MNPC_LOD_SPEC_RU.md) · [Kanban](docs/kanban/specs/KBN-0037.md).

- [M236: Location Assets — Model/Mesh ID history and Find → Replace](docs/workflows/LOCATION_ASSETS_ID_HISTORY_TWO_PHASE_SYNC_M236_RU.md)

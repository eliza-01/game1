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

**Документальный срез:** 30 октября 2026, `game1_diag_2026-10-30_13-52-46.zip` (после M162); реальные Studio состояния за пределами этого дампа не удостоверены.

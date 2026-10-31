# Навигация по документации game1

**Последняя актуализация:** 30 октября 2026 · **Основание:** `game1_diag_2026-10-30_13-52-46.zip` после M162.
**Правило:** читать актуальные контракты прежде, чем исторические milestone-отчёты. Старые тексты оставлены для причин, миграций и отладки, **не** как одновременно действующие ТЗ.

## 1. Действующие документы

| Документ | Зачем читать | Статус |
| --- | --- | --- |
| [Анимации: лицо, emotions и события](animation/README.md) | Четыре контроллера лица, Blender-маркеры, документы клипов и этап внедрения | **CURRENT / IMPLEMENTING** |
| [Актуальное ТЗ](spec/CURRENT_PROJECT_SPEC_RU.md) | Текущие возможности, socket/atlas/FBX/actor контракты, scope и Definition of Done | **CURRENT** |
| [Архитектурная карта](architecture/CURRENT_ARCHITECTURE_RU.md) | Модули, владение данными, уже выполненная декомпозиция и устаревшие предположения | **CURRENT** |
| [Рефакторинг: остаток работ](architecture/REFACTOR_ROADMAP_RU.md) | Completed/Partial/Pending, очередность, критерии и non-goals | **CURRENT PLAN** |
| [Инженерные правила](../AGENTS.md) | Обязательные архитектурные ограничения для любого кода | **CURRENT** |
| [Workflow и проверки](workflows/DEVELOPMENT_AND_VALIDATION_RU.md) | Запуск, patch apply, регрессии, Studio smoke, сохранность IDs | **CURRENT** |
| [Правила документации](workflows/DOCUMENTATION_RULES_RU.md) | Приоритет источников, история vs ТЗ и обновление ссылок | **CURRENT** |

## 2. Исторические материалы — каталог по доменам

[Все исторические документы по разделам](history/README.md).

- **Architecture M85–M105** — как реально разделяли серверный bootstrap, Host Agent, Monster, Combat, Studio Bridge. Не считать эти этапы невыполненными.
- **Actors / Combat / Animation** — NPC, monster pursuit, weapon attachment, attack loops и ранние animation contracts.
- **Location Assets / Atlas** — M117–M162, смена shared atlas, подтверждения Sync, legacy inheritance.
- **Real Estate / House Sockets** — M107–M161, FBX bones, sync, размеры, pivot, телепорт, E/F, AIM/USE.
- **Studio tooling** — authoring, preview, plots и публикационные инструменты.
- **Первоначальный Milestone 1** — первоначальный продуктовый план, не актуальный состав Asset Manager.

Два исторических артефакта остаются в корне `docs/` из-за контрактов и ссылок: [архитектурный аудит 14 октября](ARCHITECTURE_AUDIT_2026-10-14_RU.md), [CSV-инвентаризация 14 октября](ARCHITECTURE_SOURCE_INVENTORY_2026-10-14.csv). **Цифры и план из них датированы 14 октября.** Также один старый файл с нечитаемым именем `...pivot_...md` оставлен на месте из-за кодировки пути в исходном архиве; его содержательная тема доступна в [архивной заметке о фонаре и rig pivot](history/real-estate/LANTERN_ATTACHMENT_RIG_PIVOT_NOTE_RU.md).

## 3. Самостоятельные пакеты внутри репозитория

- [`docs/Eyesland_Character_Codex/START_HERE.md`](Eyesland_Character_Codex/START_HERE.md) — отдельный Blender character rig work package со своими `AGENTS.md` и технической спецификацией. Его requirements не автоматически применяются к текущему runtime.
- [`roblox_character_ui_agents/README.md`](../roblox_character_ui_agents/README.md) — автономное направление интерфейса персонажа с PRD/TECH/ART; его локальные docs сохраняются, не перемешиваются с историей основного проекта.
- [`place/README.md`](../place/README.md) — специфика сборки Place.

## 4. Как читать при противоречиях

Начать с текущего ТЗ и исходных contracts. Если отчёт M133 рекомендует `StudioRealEstateSocketRecovery`, он **устарел**: восстановление костей удалено M153. Если M146 рекомендует единую кнопку F для всех действий, для современной двери/замка применяются M159, а для лифта/сундука M161. См. раздел «Опасные устаревшие предположения» в [архитектурной карте](architecture/CURRENT_ARCHITECTURE_RU.md).

Чтобы добавить новый milestone: сохранить **отчёт** в соответствующем `history/<domain>`, а **действующий контракт** обновить в `spec/` и/или `architecture/`, затем обновить [каталог](history/README.md). Не дублировать конкурирующие «актуальные ТЗ» под разными датами.

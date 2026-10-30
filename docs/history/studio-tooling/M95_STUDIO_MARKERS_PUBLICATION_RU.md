# M95 — Studio Markers, Publication и Population Defaults

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


**База:** M94 после `game1_m94_workspace_location_bounce_after_contact.patch`.

## Границы компонентов

- **`StudioMarkerVisibility`** управляет только визуализацией авторских маркеров в Roblox Studio (точки спавна Monster/NPC, радиусы, метки и границы Location). Не изменяет регистрацию, иерархию, координаты или Pivot моделей; выбор сохраняется в настройках плагина.
- **`publication-descriptions.js`** формирует описания публикации для Character, Weapon, Monster, NPC и Location Asset из типа и имени ассета. Ввод допускает ручное редактирование. Для Location Asset сервер сохраняет защиту от повторного добавления имени.
- **`MonsterSpawnStore`** задаёт только для новых записей Monster/NPC значения `spawnRadius=15`, `maxAlive=3`. Данные существующих точек не изменяются.

## Ручные проверки

1. Переустановить Game1Bridge при закрытой Roblox Studio, открыть Studio. Кнопкой `Markers` скрыть и восстановить метки точек, радиусы и границы. Добавленная при скрытых метках новая точка тоже должна быть скрыта.
2. В Asset Manager выбрать и переименовать Location Asset: описание должно быть `Game1 Location Asset <asset name>`. Проверить публикацию остальных типов моделей и отсутствие дублирования имени.
3. В `08 · Population` создать новую точку Monster/NPC: Radius 15, Max Alive 3. Проверить, что у ранее сохранённой точки остаются её значения.

## Применение и границы проверки

Изменения UI требуют обновления Control Center; кнопку Studio — переустановки Game1Bridge. Миграции SQLite не требуются. Для автоматической проверки: `python system/verify/verify.py` и `python -m unittest discover -s system/verify -p "test_*.py" -q`. Визуальные действия плагина требуют проверки в Roblox Studio.

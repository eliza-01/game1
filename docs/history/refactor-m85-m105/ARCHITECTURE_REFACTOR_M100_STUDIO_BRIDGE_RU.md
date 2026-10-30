# M100 — Studio Game1Bridge: выделение команд и настроек

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


## Основание

Исходная версия: архив 2026-10-16 10:23 + M99. Game1Bridge.server.luau до разделения: 1862 строки. После: около 887 строк.

## Новые границы модулей

- `Game1Bridge.server.luau`: composition root, инициализация DecoManager / LocationCommands / Markers, существующий редактор Timeline, получение и диспетчеризация команд. Контракты `model-load`, `monster-spawn`, `timeline-editor`, `location-authoring` не меняются.
- `StudioModelLoadCommands.luau`: проверка команды загрузки, FBX/Roblox Asset импорт, выбор ServerStorage destination, проверка костей, шаблон персонажа, grip и texture, ответ `model-load-result`.
- `StudioActorSpawnCommands.luau`: действия `place/upsert/select/delete/sync`, маркеры Monster и NPC, интеграция `NpcSpawnPreview` и `NpcSpawnPlacement`, ответ `monster-spawn-result`.
- `StudioDebugPreferenceBridge.luau`: настройки Test Loadout, хранение через `plugin:GetSetting/SetSetting` и обмен через ReplicatedStorage.

Сервисы Roblox и токены/URL явно передаются из composition root; дочерние модули подключаются по `script.Parent.<Module>` внутри папки `modules`. Модули явно прописаны в `plugin.project.json`.

## Что оставлено без изменений

Схема команд и результатов, валидация rig и костей, монтирование импортированной модели, spawn marker metadata, порядок callback регистрации, значения URL/токенов, редактирование Timeline, DecoManager и Marker toggle.

## Гарантии и ограничения

`system/studio-plugin/install.ps1` проверяет наличие новых имён модулей в Rojo-сборке, затем сверяет SHA256 с установленным плагином. Патч не меняет runtime-сервер Game1.

Локальные проверки: `verify.py`, существующие offline тесты и контрактные тесты M100. Реальное поведение в Roblox Studio и сам `rojo build` в этой среде не запускались; после установки следует проверить загрузку Character / Monster / NPC / Weapon, CRUD точек спавна и Test Loadout preference bridge.

## Следующий этап

В `Main` ещё остаётся большой Timeline UI и polling. В дальнейшем редактор следует вынести как отдельный контроллер, а HTTP-транспорт — как переиспользуемый адаптер, отдельно от импорта моделей.

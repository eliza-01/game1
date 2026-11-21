# M403 · NPC Studio Markers / DEV Location Boundary Hotfix

## Границы ответственности

- `StudioMarkerVisibility`: существующий Studio-only переключатель `Markers` сохранён. Добавлена кнопка `NPC Spawns`, управляющая только помеченными `Game1NpcSpawnMarker` моделями, включая их Preview. Не меняет положение, принадлежность, метаданные и регистрацию точек. Состояния двух кнопок сохраняются через `Plugin:GetSetting` и `Plugin:SetSetting`; при Unloading визуальные свойства восстанавливаются.
- `Game1AuthoringCleanupService`: единственный runtime-владелец удаления редакторского `Workspace.Game1Authoring` в Play/опубликованной игре. Теперь запускается в `Game1Server/init` до ожидания `Game1Shared` и общего bootstrap; повторный вызов из ServiceCatalog идемпотентен.
- `RuntimePlaceBuilder`: после Preflight и проверенного backup исключает исключительно `Workspace.Game1Authoring` из Runtime XML. В Preflight проверяет строго один editor-owned Folder и отсутствие внешних ссылок на удаляемые экземпляры. Остальные Workspace модели, Plot, NPC registry и источники данных не меняются. В отчёт записывается `removedAuthoringInstances`; исходный `.rbxlx` и backup неизменны.

## Проверка в Studio/DEV

1. В `game1` toolbar нажать `NPC Spawns`: все метки NPC должны скрываться и возвращаться независимо от `Locations` и MonsterSpawns. Кнопка `Markers` по-прежнему переключает все категории. После нового `Restore markers` настройка должна сохраниться.
2. Запустить Studio Play: `Workspace.Game1Authoring` должна исчезнуть в runtime-копии, а после Stop сохраниться в Edit.
3. Выполнить новый `Preflight → Backup + Build Runtime draft`. Проверить, что `Game1Authoring` и `Edge_###` отсутствуют в `runtime_place.rbxlx`, а исходный `.rbxlx` и backup идентичны.
4. Переопубликовать DEV с обновлённым кодом/Runtime Place. Уже опубликованный старый DEV сам по себе не изменится. В опубликованной игре проверить отсутствие линий Locations и корректность NPC spawn.

Статические тесты не являются проверкой действительного Roblox Studio/мобильного DEV. Патч не включает публикацию и не обходит `publishAllowed=false`.

# M216 — Location Assets · аварийный откат M215 и строго адресная ID-синхронизация

**СТАТУС: CURRENT.** Перекрывает опасный контракт M215. Перед установкой восстановите повреждённый Place из резервной копии / Studio Version History. Сам M216 не способен вычислить исходные мировые координаты моделей, уничтоженных M215. Не запускайте M215 Sync повторно.

## Причина и граница исправления

M215 реализовал `DecoPlacedAssetSync.RefreshModels`, который загружал повторно FBX (`LoadAssetAsync`), клонировал новую Model, применял сохранённые `GetPivot`/`GetScale` и **уничтожил** предыдущую модель. У разных опубликованных FBX могут отличаться локальные pivots и mesh offsets; идентичный pivot новой и старой Models не гарантирует одинакового визуального размещения. Старые размещения не имели меток ревизии, поэтому это затронуло множество экземпляров.

В дополнение UI отправлял `/api/location-assets/studio-sync` без `slug`, `StudioDecoSyncCommands` разрешал глобальную `schemaVersion=1`, а `refreshRegistry()` мог менять материалы даже при открытии DecoManager. Републикация общего атласа также запускала глобальный Studio Sync. Все эти пути устранены.

## Новый контракт

1. Из раздела `Location Assets` необходимо явно выбрать **один** опубликованный slug. `Sync selected asset IDs` запрещён для неопубликованных ассетов; вызов без slug отклоняется HTTP 400. Любые старые глобальные команды `schemaVersion=1/2` отклоняются. Host Agent использует только Bridge `schemaVersion=3` с `targetSlug`, `bindingRevision`, `modelAssetId`, `atlasAssetId`; Studio повторно проверяет идентификаторы по свежему реестру.
2. Изменения разрешены **только** в `Workspace/Game1DecoAssets/**`, только на Models с атрибутом `Game1DecoAssetSlug == targetSlug`. Никакого массового Workspace/ServerStorage сканирования для мутации. Плагин никогда не пересоздаёт и не переподвешивает размещённые Models или MeshParts, не меняет PivotTo/ScaleTo/CFrame/Size/Anchored/CanCollide/bones, не вызывает `ApplyMesh`.
3. Для существующих MeshPart меняются только `TextureID` и, если SurfaceAppearance уже существует, его `ColorMap`. `AlphaMode` не меняется, новые SurfaceAppearance не создаются. Модель получает метаданные-ссылку `Game1DecoRegistryModelAssetId` (опубликованный Model ID), **не** перезаписывая `Game1DecoPublishedModelSha256`.
4. `MeshPart.MeshId` является read-only в Luau. `MeshPart:ApplyMesh` обновляет также геометрию коллизий, следовательно не соответствует требованию «только ID». M216 **не применяет изменённую геометрию FBX**. Вместо ложного успеха сообщает `pendingGeometry` — число размещений с несовпадающей/неизвестной ревизией FBX. Для переиздания геометрии потребуется отдельный, явно разрешённый и проверенный в Studio workflow.
5. История аудита существует на трёх уровнях: атрибут `Game1DecoSyncHistory` внутри каждого изменённого размещения (только 32 последних операции), append-only WAL `.control-center/location-asset-studio-sync-history.jsonl` и полная нормализованная MySQL 8.4 история M217. MySQL хранит операцию и каждое реально изменённое размещение с `instanceId`, Studio path и парами old/new Model reference либо Atlas Image ID. `GET /api/location-assets/studio-history?slug=...` постранично читает MySQL; UI загружает все страницы. См. `ASSET_REPLACEMENT_AUDIT_M217_RU.md`.
6. `Republish atlas` обновляет публикацию и переводит всех потребителей общего варианта в состояние pending, но **не вызывает Studio Sync автоматически**. Автор самостоятельно открывает нужный asset и синхронизирует его. Подраздел Real Estate использует собственный штатный целевой Studio Sync.
7. Для изменений от Host Agent имеется Studio Undo waypoint до и после работы. При ошибке записи журнала в Host Agent синхронизация не получает статус `synced`; Studio остаётся источником локального атрибута-истории. Если Host Agent потерял ответ, не повторяйте Sync без проверки Place/Studio Undo.

## Первая проверка (ОБЯЗАТЕЛЬНО НА КОПИИ PLACE)

1. **Восстановить резервную копию Place** после инцидента M215; сохранить её под новым именем. Остановить старый Host Agent, применить M216, переустановить Studio plugin, закрыть Studio полностью и открыть копию Place.
2. Выбрать один опубликованный Location Asset, например `bush_01`. Записать `GetPivot()`, `GetScale()`, `Parent`, число и полный список MeshParts, `CFrame`, `Size`, `MeshId`, `TextureID`, `CanCollide`, `Anchored` для 2 экземпляров этого slug и соседнего slug.
3. Нажать `Sync selected asset IDs`. Должен быть выбран только `bush_01` (`targetSlug` в ответе). Другой slug не меняется даже при общем атласе. Не создаются и не удаляются модели, все CFrame, Scale, Parent, Size, MeshId и физические свойства неизменны.
4. Если у выбранного ассета изменился опубликованный Atlas ID, обновятся только `MeshPart.TextureID` и существующий `SurfaceAppearance.ColorMap`. Если поменялся FBX — отчёт содержит `pendingGeometry`, без автоматического сдвига/перестройки объектов.
5. Проверить `Studio ID replacement history` и атрибут `Game1DecoSyncHistory` у размещения. Повторный Sync без изменений не должен дописывать изменения ID.
6. Вручную проверить Studio Undo, сохранение Place и повторное открытие. Лишь после этого использовать на рабочей карте.

## Восстановление и откат

- Если *уже* применён M215 к Place: восстановить Place из резервной версии или Roblox Studio Version History. Встроенный layout `Save Assets Data` может хранить pivots экземпляров, но M216 автоматически не расставляет модели по этому файлу, чтобы не усугубить потерю геометрии.
- `git apply -R` M215 поверх изменённого M215 проекта может вернуть код M214, но **не восстановит Place**. M216 — прямой патч поверх M215: откат опасного поведения и добавление аудита в одном наборе изменений.
- База Open Cloud и опубликованные Roblox IDs не меняются. JSONL служит write-ahead log и источником идемпотентной миграции в MySQL M217; его необходимо сохранять вместе с SQL backup. SQLite в этот контур не входит.

## Ограничение проверки

Python, JS, validators и применение Git-патча можно проверить без Roblox Studio. Физические CFrame и фактическое поведение Studio Undo требуют выполнения smoke-теста в настоящем Studio на копии Place. **Не считать этот тест пройденным до выполнения.**

# M221 · Location Assets: защищённая синхронизация геометрии размещённых MeshPart

**Статус: ОТМЕНЁН M222; НЕ ИСПОЛЬЗОВАТЬ.** Исторический контракт Studio Sync, supersedes **only** M216 prohibition on *any* ApplyMesh and M220's reference-only limitation. All M216 restrictions on global sync, placed Model replacement, transforms, scope and audit remain mandatory. **Реальная Studio-проверка обязательна** — Python/Luau preflight её не заменяет.

## Причина и принцип

M216/M219/M220 обновляли только `MeshPart.TextureID`, `SurfaceAppearance.ColorMap` и метаданные `Game1DecoRegistryModelAssetId`. Новый FBX в DecoManager правильно загружался через Model Asset ID, но уже размещённые MeshPart сохраняли старый `MeshId`. `Game1DecoPublishedModelSha256` оставался старым, отчёт показывал pendingGeometry.

M215 **удалял исходные размещённые Models** и загружал новые. Из-за разницы FBX pivot были смещены сотни объектов. **Этот механизм не возвращаем.** M221 использует документированный Roblox `MeshPart:ApplyMesh(sourceMeshPart)`, который применяет меш к **уже существующему MeshPart**. Других путей сменить `MeshId` обычным присваиванием нет. Метод одновременно обновляет MeshContent, TextureContent, MeshSize и collision fidelity/internal collision geometry — это реальное обновление геометрии, не «чистая замена ID».

## Граница ответственности

- `DecoManager`: единственный координатор явной команды Sync; общий `DecoAssetLoader` скачивает одну актуальную опубликованную модель из Roblox Open Cloud, только если есть устаревшие размещения.
- `DecoPlacedAssetSync`: выбор только указанного slug, сбор атомарного плана, истории и metadata, коммит/rollback.
- `StudioMeshInPlaceSync`: доменно-независимый алгоритм отображения *часть ↔ часть*, проверки локальных CFrame и применения `ApplyMesh` в существующий MeshPart; пригоден для переиспользования, не меняет Place структуру.
- `StudioTextureAppearance`: общая смена ID текстуры/ColorMap в строгом режиме.
- `studio_deco_bridge.py` / `StudioDecoSyncCommands`: **schemaVersion 4**. M216–M220 плагин версии 3 не принимает команду 4 — поэтому не сможет выдавать «успешно» при обновлении только атласа. Нужна переустановка Studio Plugin.
- `LocationAssetSyncHistory` и MySQL M217: журнал `model` (реально применённый FBX Model Asset ID), `model_reference` (изменение ссылки без геометрии), `atlas` (смена Image ID) по каждому размещённому `instanceId`. Ранее накопленная история не удаляется, миграция схемы не требуется.

## Предпроверка до изменений

1. Команда проходит только в Studio Edit Mode и требует конкретный slug, Model ID, Atlas ID, bindingRevision.
2. Находятся лишь размещённые Models с `Game1DecoAssetSlug == slug` и непустым `Game1DecoInstanceId`; `Game1Authoring` и Camera исключены.
3. Геометрия считается актуальной при совпадении `Game1DecoPublishedModelSha256`. Для остальных скачивается опубликованный Model через один loader.
4. **Для каждого** старого экземпляра: количество и уникальные относительные пути MeshPart должны совпадать с исходником. Вложенные Bones/WrapLayer/WrapTarget отказывают: скелеты и деформации нельзя обновлять этим workflow. Относительные CFrame всех MeshPart, нормализованные по Scale, сравниваются относительно первой части, **не** нестабильного импортного Model pivot.
5. Создаются unparented копии исходных MeshParts для rollback. Они не заменяют размещённые объекты, удаляются после завершения.
6. Если импорт отличается структурой, именами, локальными координатами или не загрузился — **весь Sync отклоняется до изменения Place**. Нет fallback на M215 «новая модель целиком».

## Коммит и результат

- `MeshPart:ApplyMesh()` в прежний объект. Восстанавливаются исходные `CFrame` и `Size`; затем дополнительно проверяются сохранённые `Model:GetPivot()/GetScale` и parent. Если изменились — ошибка и попытка rollback. Name, `Game1DecoInstanceId` и дочерние внешние объекты не меняются.
- Обновление текстуры применяется общим `StudioTextureAppearance` после меша.
- Только после успешного применения всех частей обновляются `Game1DecoPublishedModelAssetId`, `Game1DecoPublishedModelSha256` и registry reference. История получает событие `kind=model` со старым и новым **Model Asset ID**, не MeshPart.MeshId.
- Возвращаются `geometryUpdated` (количество экземпляров), `meshPartsUpdated` (количество MeshPart), `pendingGeometry` (ожидает/не подтверждена), `parts` (смены Image ID), `replacedModels=0` (замен размещённых Model нет).
- При ошибке — попытка откатить mesh content/collision через сохранённые снимки, ID/атрибуты/историю. Ошибки отката явно возвращаются, никогда не скрываются. Studio ChangeHistoryService создаёт waypoint перед/после операции.

## Оставшийся принципиальный риск

**Невозможно доказать неизменность визуального положения вершин произвольного нового FBX только по CFrame/Size и именам MeshPart.** Обновлённый FBX может изменить внутренний origin/смещения вершин внутри MeshPart при неизменных внешних параметрах. Контракт отклоняет известные структурные и трансформационные несовместимости, но не гарантирует отсутствия каждого визуального сдвига. `ApplyMesh` обновляет и коллизионную геометрию; для skinned mesh/изменённого рига нужна отдельная процедура. Не используйте массовый Sync на продакшн Place без Studio smoke на копии.

## Студийный smoke перед применением к основному Place

1. Открыть копию `.rbxl/.rbxlx` из бэкапа **в Edit Mode**. Выбрать тестовый slug с двумя старыми экземплярами и третьим — другого slug. Сохранить до Sync `CFrame`, `Size`, `MeshId`, `Model:GetPivot()`, `Model:GetScale()`, instanceId и дерево потомков.
2. Переустановить плагин, перезапустить Host Agent, открыть Studio заново. Опубликовать изменённый FBX, нажать **Sync Studio именно у этого Location Asset**.
3. Проверить `geometryUpdated=2`, `meshPartsUpdated>0`, `pendingGeometry=0`. При изменённом FBX проверить отличающиеся `MeshId` в размещённых MeshPart. `CFrame`, `Size`, scale, instance ID, parent у обоих экземпляров должны остаться прежними. Третий slug совершенно не затронут.
4. Проверить atlas republish отдельно, повторный Sync без изменений (`geometryUpdated=0`, `parts=0`) и `Database → Asset History` с историей Model и Atlas ID.
5. Проверить несовместимую структуру новой FBX: Sync должен завершиться читаемой ошибкой и не менять ни одну размещённую часть. Проверить Undo и резервную копию Place.
6. Только после этого тестировать массовые экземпляры одного slug, затем сохранять продакшн Place. Если `ApplyMesh`/Undo ведут себя иначе в Studio — остановиться и прислать Studio Output, не публиковать Place.

## Откат

Остановить Host Agent и Studio; применить Git reverse patch M221 и переустановить плагин предыдущей ревизии. Для уже применённой геометрии кодовый откат **не возвращает старые меши**: отменить Studio Undo или открыть резервную копию Place. История ID остаётся в MySQL/JSONL, не стирается.

Ссылки: Roblox Creator Hub `MeshPart:ApplyMesh` и `AssetService:LoadAssetAsync` (https://create.roblox.com/docs/reference/engine/classes/MeshPart/ApplyMesh и https://create.roblox.com/docs/reference/engine/classes/AssetService).

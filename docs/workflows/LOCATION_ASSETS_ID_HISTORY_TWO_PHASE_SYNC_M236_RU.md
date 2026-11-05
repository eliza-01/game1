# M236 — Location Assets: published Model / MeshPart ID history, Find → Replace

## Цель

Ранее Studio Sync ошибочно требовал совпадающие имена или пути MeshPart между
старыми и вновь опубликованными FBX (`StudioAuthoringMeshAnchor.Match`).
Название и путь Blender-объекта могут измениться, поэтому соответствие по ним
не может быть обязательным для обновления.

## Источники идентификаторов

- `Model Asset ID`: версии публикаций в `location_asset_publications`, SQLite.
- `MeshPart.MeshId`: **отдельный** идентификатор отдельного Roblox-меша внутри
  опубликованной Model. Извлекается из неизменяемых версий через
  `AssetService:LoadAssetAsync()` в Roblox Studio, а не вычисляется из Model ID.
- `Atlas Image ID`: активная привязка из общего Atlas Registry; публикация модели
  не публикует и не изменяет атлас.
- `location_asset_mesh_id_inventory`: кэш фактически считанных Roblox Mesh ID
  **для каждой опубликованной версии Model**, с числом повторов каждого ID.
- `Game1DecoPublishedModelAssetId`: ID версии размещённого экземпляра.
- `Game1DecoSyncHistory`: последние 32 операции на самом экземпляре, включая
  `meshIdsBefore` и `meshIdsAfter`; полная история — JSONL и MySQL M217.

## Две фазы Studio Bridge (schema 7)

### 1. Find Mesh IDs (phase=scan)

Asset Manager передаёт только slug и список версий опубликованной Model.
Plugin получает Mesh IDs из исходных Model, ищет совпадения среди MeshPart во
всём Workspace и вызывает `Selection:Set(found)`. Возвращает счётчики
`selectedMeshParts`, `managedMeshParts`, `unmanagedMeshParts`, `managedModels`,
`geometryPending`, `texturePending`, `mode`, `inventory` и одноразовый токен.

**Ни одной модели, текстуры, физического свойства, координаты или записи
об успешной Studio Sync на этом шаге не меняется.** Кэш Mesh ID можно обновить.

Поиск может подсветить части других ассетов с общим MeshId — это диагностика,
**не разрешение** их заменять. Изменения допускаются только для managed roots
с `Game1DecoAssetSlug=<selected slug>` и `Game1DecoInstanceId`.

### 2. Replace (phase=replace)

Тип кнопки определяется обнаруженными изменениями:

| Model/Mesh изменился | Атлас изменился | Кнопка |
|---|---|---|
| нет | да | Replace Texture |
| да | нет | Replace Mesh |
| да | да | Replace Texture + Mesh |
| нет | нет | Already up to date (disabled) |

Плагин принимает действие только при совпадении токена Find, slug, публикаций,
корневых преобразований и снимков Mesh ID/текстур/ColorMap каждой размещённой
части. Токен одноразовый; повторять при ошибке можно только после нового Find.

Изменение геометрии выполняется **тем же `StudioManagedRigSwap`**, что и Real
Estate. Старый опубликованный Model ID загружается как исторический источник
авторского преобразования. Если он не записан в атрибутах экземпляра,
версия из истории определяется только по **полному совпадению набора Mesh ID
с количествами**, а не по одному общему коллайдеру. Уникальные старые
MeshPart.MeshId затем используются
для установления соответствия с уже размещённым экземпляром. **Совпадения имён
старой и новой публикации не требуется.** Все managed child rigs заранее
подготавливаются и проверяются; корневая Model не удаляется и не пересоздаётся.

Если не удаётся однозначно определить историческое преобразование, либо
в размещённом корне обнаружена неизвестная геометрия, операция останавливается
до изменения Place. Исключения при применении проходят через Rollback
общего `StudioManagedRigSwap`.

## Журнал

В JSONL сохраняются фактические события публикации и Sync, старый/новый
Model ID и Atlas ID, а для каждого изменённого экземпляра — множества
`MeshPart.MeshId` с количеством применений до/после. В MySQL эти множества
записываются в `asset_replacement_operations.metadata_json.meshIdRevisions`;
основные события по Model/Atlas ID остаются в прежних индексируемых таблицах.
Не создаётся выдуманная попарная связь между старыми и новыми MeshPart разных
по структуре моделей.

## Область ответственности

- Atlas Registry: публикация/привязка текстур.
- LocationAssetStore: версионированные публикации и кэш инвентаря Mesh ID.
- StudioPublishedMeshHistory: ID scan, selection, historical alignment proofs.
- DecoPlacedAssetSync: доменный поиск/проверка slug и план замены.
- StudioManagedRigSwap: общая транзакция RigSwap/Undo/Rollback Real Estate + Location.
- Studio Bridge: transport schema7 и одноразовый preview token.
- Asset Manager: число найденных частей, ID всех публикаций и автоматическое
  имя кнопки по фактическим различиям.

## Проверки и ограничения

Статические, серверные и UI-тесты не эквивалентны проверке в Studio. Первый
Replace выполнять на копии Place, сохранить Position, Orientation, Pivot,
Scale, Mesh ID и Image ID нескольких экземпляров одного slug и контрольного
экземпляра другого slug. Если новая версия FBX физически переносит вершины
относительно авторского origin, даже успешный RigSwap может визуально изменить
положение частей — новая версия геометрии должна сохранять авторские координаты.

Это не операция подмены `MeshPart.MeshId = ...` и не `ApplyMesh`.

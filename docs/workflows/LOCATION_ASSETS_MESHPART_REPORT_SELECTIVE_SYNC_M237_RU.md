# M237 — Location Assets: Mesh/Texture scan по частям, Select / Sync

## Причина

В M236 `StudioPublishedMeshHistory.Scan()` не сверял `TextureID` и `SurfaceAppearance.ColorMap`
у `COL_*` MeshPart, а `DecoPlacedAssetSync.RefreshIds()` пропускал их при записи.
Поэтому старый Image ID на `col_mesh` мог существовать одновременно с `Already up to date`.
Кроме того, `Found 1 MeshPart` учитывал прежде всего исторические несовпадения Mesh ID,
а все 5 управляемых экземпляров учитывались отдельно — без построчного отчёта.

## Правило проверки

После `Find Mesh IDs · Studio` каждая физически обнаруженная часть активного
`Game1DecoAssetSlug` показывается самостоятельно, включая коллайдеры. Идентификаторы:

- `Model ID` — текущий опубликованный Model Asset ID.
- `Current Mesh IDs` — **все** MeshPart.MeshId текущей опубликованной Model, из неизменяемого ID inventory.
- `Current Texture ID` — Image ID текущей привязки к Atlas Registry.
- `Mesh ✓/✕` — фактический MeshId присутствует / отсутствует в списке актуальных ID.
- `Texture ✓/✕` — фактический TextureID и, если есть, ColorMap совпадают по числовому Image ID.

Для отличающейся Model SHA или Model ID может потребоваться обновление всей
управляемой модели даже при повторном использовании её отдельных Mesh IDs.
Такие части отмечаются как `Model publication revision differs`.

У каждой строки показаны имя, путь в Studio, фактические Mesh/Texture/ColorMap ID,
проверка и управляемая принадлежность. Исторические совпадения **вне текущего slug**
отображаются только для диагностики и не могут быть выбраны для изменения.

## Действия

- `Find` только читает и выбирает найденные MeshParts через `Selection:Set()`; Place не меняется.
- `Sync` в строке — только эта выбранная часть; `Select` позволяет сформировать пакет.
- `Select all pending`, `Clear selection`, `Sync selected`, `Sync all` — явные операции.
- Точная операция `Replace Texture`, `Replace Mesh`, `Replace Texture + Mesh`
  вычисляется автоматически из выбранных строк; никаких ручных переключателей mode.
- Для одной устаревшей текстуры можно обновить `TextureID`/существующий `ColorMap`
  **только у выбранного MeshPart**.
- Если у выбранной части требуется обновление модели, из-за Bone/Wrap/rig
  обновляется **весь управляемый дочерний rig** её размещённой корневой модели
  через существующий `StudioManagedRigSwap`. Никаких отдельных ApplyMesh,
  перемещений, удаления или замены корня.
- Scan token одноразовый, выбор сверяется с серверным сканом в Studio;
  идентификаторы, transform и привязка повторно проверяются перед записью.
- Для частичной операции `AtlasRegistry.mark_synced` НЕ вызывается. Только выбор,
  охватывающий все pending managed MeshParts данного скана **или целые rig**
  через выбранную геометрическую замену, может подтвердить синхронизацию всей привязки. После частичной операции нужен повторный Find.

## Границы

Studio подтверждается только фактической Edit-mode проверкой на копии Place;
исходный проект в дампе не содержит Place с полноценными моделями. Никакой
новой таблицы SQLite, фоновой публикации, глобального Sync или новых Model IDs.
Области: `StudioPublishedMeshHistory` (скан), `DecoPlacedAssetSync` (выбранная
транзакция), `DecoManager` (одноразовый выбор), `StudioDecoSyncCommands` (transport),
`studio_deco_bridge.py` (проверка контрактов), `location-asset-workflow.js` (UI).

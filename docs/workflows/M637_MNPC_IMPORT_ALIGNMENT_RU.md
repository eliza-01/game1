# M637 · MNPC Studio Import & Alignment

Общий authoring-only контракт Monster/NPC поверх M636. Runtime, AI, OBB и demand pilot не изменяются. Статус A07 NOT_RUN.

## Порядок

LOD Manager → MNPC → Capture idle & geometry → Bake & stage LOD1 → Publish LOD1 → **Verify import & alignment · Studio** (Studio Edit, установленный Game1Bridge). Не требуется запуск Play. Проверка не публикует новые модели/атласы, не меняет Place, не оставляет временные экземпляры.

## Контракт

- Автоматическая привязка только для M636 `captured_idle` с `rootSpace=roblox_navigation_studs_y_up`. Ручные FBX не имеют подтверждённого origin/единиц, поэтому не допускаются к автопривязке.
- Blender перечитывает immutable staged FBX тем же инспектором M633; возвращает вершины в Blender scene coordinates. Инверсия M636 `[x,-z,y]` восстанавливает root-space studs `[x,z,-y]`. Отчёт проверяется против сохранённого отчёта FBX.
- Studio Edit загружает опубликованный Model через AssetService, не parent в Workspace; требует ровно один MeshPart `lod1`, отсутствие Animator/Bone/Humanoid/AnimationController, скриптов и skin weights. EditableMesh возвращает вершины используемых треугольников в локальном пространстве детали, с учётом Size/MeshSize. EditableMesh и модель уничтожаются также при ошибке.
- Host сопоставляет оба множества вершин (duplicate split vertices разрешены) в обе стороны с пространственным hash; перебирает 24 proper signed axis rotations, положительный uniform scale и translation. Сравнивает число треугольников; допуск вершин 0,001–0,02 studs по диагонали. При неоднозначности (симметрия), изменении точек, отражении асимметричной геометрии, произвольном повороте вне поддерживаемых осевых или анизотропном масштабе отказывает. Это не проверка порядка треугольников/нормалей/UV или визуального рендера.
- Один revision-pinned результат внутри текущего `geometry_json.alignment`: schemaVersion, identity(kind/slug/revision/FULL fingerprint/source SHA/Model ID/Image ID), meshId, meshSize, size (локальные оси детали), rootCFrame (translation + proper 3×3 matrix), scale, maxVertexError, tolerance, triangles, referenceSha256. Не подменять Mesh ID идентификатором Cloud Model. Runtime сможет создавать локальный MeshPart указанного meshId/size и размещать его `root.CFrame * CFrame.new(table.unpack(rootCFrame))` после проверки своей import/appearance цепочки. Image ID закреплён в identity, но реальная доступность/UV/цвет ещё не проверены.
- HTTP POST `/api/lod-manager/mnpc/{kind}/{slug}/align` принимает только expectedRevision. Bridge `mnpc-align-v1` переиспользует локальный транспорт M635, operation identity и лимит результата. При stale/full/idle/atlas/source mismatch не отдаётся current alignment; ошибка не перезаписывает предыдущий успешный отчёт. Новый stage очищает alignment, повтор идентичного результата не пишет историю. Нет отдельной таблицы/реестра.

## Приёмка и следующий этап

`alignmentStatus=GEOMETRY_VERIFIED` означает только успешное математическое сопоставление при фактическом запуске инструмента. `runtimeReady=false`, `runtimeEnabled=false` остаются намеренно. Настоящий Roblox/Blender import, UV, цвет, визуальная поза и соответствие масштаба на сцене не проверены в диагностической среде. Python SQLite/geometry/HTTP doubles и UI smoke не заменяют их. Следующий этап: runtime asset export/manifest и client visual lifecycle, с отдельным guard визуальной готовности и изоляции репликации. Production FULL сохраняется.

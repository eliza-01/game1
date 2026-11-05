> **Superseded by M232** for the Location COL_* fidelity and the authoring UI. Read `LOCATION_ASSETS_FBX_AUTHORING_M232_RU.md`.

# M231 — Location Assets · общий анализ FBX, COL, glass и скелет

## Границы

- **Один анализатор костей:** `system/asset-manager/fbx_mesh_inspection.py` вызывается и Real Estate, и Location Assets; в нём не меняются FBX, rest pose и веса. Арматура определяется **по связи** с Mesh через parent/modifier, а не по похожему имени.
- **Один авторский классификатор:** `services/mesh_authoring_policy.py` определяет `COL`-токены и стекло по имени объекта. `COL_foo`, `col_mesh`, `foo_COL_01`, `house_col` — коллайдеры. Имена типа `color` — нет. Стекло определяется `*glass*` (регистронезависимо), кроме `COL_*`.
- **Один Studio-записыватель физики:** `src/shared/world/MeshPhysicsCore.luau`, подключённый в Studio-плагин как `StudioMeshPhysicsCore`. Разделы различаются только политикой: Real Estate сохраняет M207 с `PreciseConvexDecomposition` для всех collidable MeshPart; Location Assets использует `Box` **только** для выделенного `COL_*` физического меша (по запросу автора).
- Location FBX **не** разбивается на отдельные Model Assets: вся иерархия и кости импортируются одним опубликованным Model Asset и обновляются общим `StudioManagedRigSwap` из M222.

## Location FBX · роли мешей

| Роль | Условие | CanCollide | CanQuery | CanTouch | DoubleSided | CollisionFidelity | Визуал |
|---|---|---|---|---|---|---|---|
| `collider` | `COL_*`, `*_COL_*`, `*_col` | true | true | false | true | `Box` | Прозрачный (`Transparency=1`, без теней) |
| `visual` | Есть хотя бы один collider | false | false | false | true | `Box` | Без изменения текстуры/геометрии |
| `glass` | Есть collider | false | false | false | true | `Box` | Незначительная прозрачность, сохранение атласа |
| `glass` | Нет collider | true | true | false | true | `PreciseConvexDecomposition` | Незначительная прозрачность |
| `visual` | Нет collider | Сохранить опубликованное | Сохранить опубликованное | false | true | Сохранить опубликованное | Без изменений |

`CanQuery=false` применяется только при `CanCollide=false` в порядке, допустимом Roblox. Для `COL_*` `Box` дешёвый, но это **bounding-box collision**, а не точная геометрия: применять только к заранее авторски подготовленным простым коллайдерам. Поведение существующих домов M207 не меняется.

### Важное о прозрачности

Стекло обнаруживается как визуальный меш. В его `SurfaceAppearance` продолжают использоваться опубликованный Atlas ID и `AlphaMode` из общей `StudioTextureAppearance`. Политика не переписывает изображение, UV или `MeshId` и не создаёт отдельный атлас для glass.

## Инспекция, история и совместимость

- Новая регистрация или `Edit → Save FBX revision` выполняют Blender-анализ **перед** сохранением изменений. Ошибка Blender/FBX отменяет регистрацию модели, а не сохраняет ложный отчёт.
- Для старых записей `Edit → Model · FBX → Analyze saved FBX` анализирует уже зарегистрированный канонический файл, не публикует его и не увеличивает ревизию.
- Отчёт на ревизию исходника хранится в `assets/manifests/location-assets-fbx/<slug>.json`, содержит SHA-256 и выводится в `fbxAnalysis` текущего ответа API только если SHA совпадает. Если файл изменился, старый анализ не подмешивается.
- В отчёте перечислены меши, роль/физика, `armature`, кости с `parent` и `matrixLocal`, а также `influencedBones`; `unassignedArmatures` не скрываются.
- Studio применяет физику к импортированным шаблонам и новым размещениям; игровой Runtime использует этот же модуль. Поворот, масштаб и позиция не меняются.
- Для уже размещённых экземпляров **явный адресный Studio Sync** выбранного slug обновляет физику только у MeshPart, перечисленных в SHA-связанном FBX-отчёте, даже когда геометрия не менялась. Перед этим снимается снимок физических свойств, предусмотрен откат при ошибке. Добавленные вручную MeshPart без имени из FBX не затрагиваются.
- Старые Location Assets без анализа остаются читаемыми с `fbxAnalysis = null`: физика уже размещённых объектов не меняется до явной инспекции канонического FBX через `Analyze saved FBX` и последующего Sync. Глобального пересохранения Place нет.

## Проверка в Studio

1. На тестовой копии Place зарегистрировать FBX с `visual`, `glass` и `col_mesh`, а также `Armature/Bone`.
2. В `Edit` сверить иерархию костей и роли; опубликовать Model/Atlas.
3. В DecoManager загрузить и разместить одну копию, проверить на каждом MeshPart свойства и отсутствие изменения CFrame/Size.
4. FBX без `COL` должен сохранить исходные коллизии обычных мешей; `glass` по умолчанию отдельный физический меш.
5. Убедиться, что Real Estate `house`, `door`, `glass` и `COL_*` по-прежнему имеют Precise, если collidable.

Реальная работа Blender, Open Cloud и Studio в изолированной среде не проверяется; автоматические тесты не заменяют эти испытания.

Runtime `EnvironmentAssetService` повторно применяет тот же модуль при запуске игрового сервера и не сбрасывает `CanQuery=false` у визуальных мешей.

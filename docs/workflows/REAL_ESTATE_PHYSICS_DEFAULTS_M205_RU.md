# M205 — параметры физики Real Estate в UI и Studio

Исправление M204: визуальная дверь и стекло не должны принудительно получать `CanCollide=false` и `Box`.

| Часть | CanCollide | CanTouch | CanQuery | CollisionFidelity | DoubleSided |
|---|---|---|---|---|---|
| `door`, `door_*` | true | false | true | PreciseConvexDecomposition | true |
| `*glass*` | true | false | true | PreciseConvexDecomposition | true |
| `COL_*`, `*_col`, `*_col_*` | true | false | true | PreciseConvexDecomposition | true |
| остальные визуальные | false | false | false | Box | true |

## Источник настроек

Control Center → Real Estate → 02 · Mesh textures показывает для **каждой** части `No Collide`,
`Collision Fidelity`, `DoubleSided` и расчётный статус `CanCollide / CanTouch / CanQuery`.
Разрешено менять `No Collide`, `Collision Fidelity`, `DoubleSided` для любой части, в том числе COL.
`CanQuery` вычисляется из `CanCollide`, поскольку Roblox не позволяет выключить пространственные запросы
для коллизионной детали. `CanTouch=false` для всех частей; события Touched не участвуют в этой системе.

Серверная нормализация в `real_estate.store.mesh_options` задаёт значения по умолчанию, если в
старой записи их нет. Любое ранее явно сохранённое `noCollide` или новые физические настройки
остаются приоритетными. В `meshOptions` сохраняются `collisionFidelity` и `doubleSided`.

Единственный writer для MeshPart — `StudioRealEstateCollisionPolicy.Apply`. Он используется
при полном Studio Sync, при обновлении отдельного MeshPart и при обновлении размещённых копий.
Вся геометрия COL остаётся невидимой и помеченной `Game1RealEstatePhysicsOnly`; игрой по-прежнему
управляют существующие системы коллизий и контакта оружия.

Никаких изменений Asset ID, FBX, bone/socket, Atlas Registry или процесса публикации нет.
Чтобы обновить ранее размещённые объекты, нужен Studio Sync после установки обновлённого плагина.

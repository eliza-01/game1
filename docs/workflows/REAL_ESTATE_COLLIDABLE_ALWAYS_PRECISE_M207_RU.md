# M207 — Real Estate: Precise при включённой коллизии

Для всех частей Real Estate, включая визуальные `house`, `door`, `window_frames_glass`, `restoration` и `COL_*`, действует инвариант:

- `CanCollide=true` → **`CollisionFidelity=PreciseConvexDecomposition`**.
- `CanCollide=false` → прежний выбранный режим Fidelity разрешён; по умолчанию `Box` у визуальной геометрии и `Precise` у `door`, `glass`, `COL_*`.
- `CanTouch=false`, `CanQuery=CanCollide` и `DoubleSided` сохраняют контракт M205.

Изменение проходит через три уровня: UI сразу выставляет `Precise` и блокирует выбор Fidelity при активной коллизии; API нормализует уже записанные `Default`, `Box` или `Hull`; Studio Sync повторно гарантирует инвариант при получении старого payload.

**Миграция SQLite не нужна**: сервер применяет нормализацию при чтении и сохранении, а Studio — при Sync. Старые вручную выключенные флаги `No Collide` остаются как были. Структура FBX, публикация, Atlas Registry и игровые системы не меняются.

Чтобы обновить уже размещённые дома: установить обновлённый Studio-плагин, выполнить Full Studio Sync. Статические тесты не заменяют проверку столкновений и открывания дверей в Studio Play.

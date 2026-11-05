# M232 — единый FBX inspection и Mesh Physics authoring

M232 исправляет разрыв M231 между анализом в Host Agent и визуальным управлением им в Asset Manager. **M231 описывал `COL_* → Box` ошибочно: M232 отменяет это правило.**

## Единые компоненты — без копий алгоритмов

| Слой | Единый контракт | Вызов из Real Estate | Вызов из Location Assets |
|---|---|---|---|
| Blender | `fbx_mesh_inspection.describe_mesh` — имена, bones, parent/rest matrix, weighted influences | `analyze_real_estate_fbx.py` | `analyze_model_fbx.py` |
| Host Agent | `services.fbx_blender_report.run_report/inspect_report` — запуск Blender, JSON и диагностика | `/api/real-estate/inspect` → `real_estate.fbx.inspect` | `/api/location-assets/inspect` → `LocationAssetStore.inspect_source_fbx` |
| Physics authoring | `services.mesh_authoring_policy` — имена COL/glass, валидация и выбор fidelity | `real_estate.collision_policy` и `mesh_options` | `LocationAssetStore` (`mesh_options_json`) |
| UI | `mesh-authoring.js` — общие defaults/normalization, контролы fidelity, bone list | `real-estate.js` | регистрация и `Edit → Model · FBX` |
| Studio/Runtime | `src/shared/world/MeshPhysicsCore.luau`, единственный записыватель physics MeshPart | `StudioRealEstateCollisionPolicy` | `DecoAssetLoader`, `DecoAssetPreparation`, `DecoPlacedAssetSync`, `EnvironmentAssetService` |

### Выбор нового FBX

1. `Location Assets → Register → Choose FBX` запускает **только анализ**, а не сохранение, публикацию или Studio Sync.
2. Под выбором файла появляется отчёт: имя исходного FBX, каждый MeshPart, тип `COL/glass/visual`, количество вершин, Armature, parent каждой кости и weighted influences.
3. Для каждого меша доступны **No Collide**, **Collision Fidelity**, **DoubleSided**, **Glass** (не для COL). Значения `CanQuery` и `CanTouch` вычисляются централизованно.
4. Сохранение нового ассета анализирует выбранный FBX повторно на сервере и принимает параметры только существующих мешей. Одна регистрация — один набор настроек и одна версия исходника.
5. `Edit → Choose replacement FBX` аналогично показывает отчёт **до** Save FBX revision. `Edit → Save mesh settings` сохраняет настройки отдельно, не создаёт новый Roblox Model ID и не трогает Studio. `Edit → Analyze saved FBX` остаётся для ранее зарегистрированных FBX.

### Физика (M207, общая неизменная инварианта)

| Меш | По умолчанию | CanCollide | CanQuery | CanTouch | CollisionFidelity | DoubleSided |
|---|---|---|---|---|---|---|
| `COL_*`, `col_mesh`, `*_col` | физический коллайдер | true | true | false | **PreciseConvexDecomposition** | true |
| Visual при наличии COL | визуальный | false | false | false | **Box** | true |
| Glass при наличии COL | визуальный | false | false | false | **Box** | true |
| Visual без COL (новая регистрация) | самостоятельный solid | true | true | false | **PreciseConvexDecomposition** | true |
| Glass без COL | glass solid | true | true | false | **PreciseConvexDecomposition** | true |
| Любой MeshPart с вручную включённым `No Collide` | визуальный | false | false | false | **Box** по умолчанию; при желании можно выбрать иной | редактируется |

**Любой `CanCollide=true` принудительно переключает fidelity на `PreciseConvexDecomposition`**; это и валидируется сервером, и применяется в Lua. Настройка `Box` для `COL_*` M231 **отменена**. `COL_*` получает `Transparency=1`, `CastShadow=false` и не потребляет atlas. Настройка Glass управляет минимальной визуальной прозрачностью, а не геометрией или atlas.

#### Совместимость старых моделей

Для старых записей без `mesh_options_json` в SQL добавляется поле **без сброса записей** и с предварительным SQLite backup `.control-center/backups/location_mesh_options_m232_*.sqlite`. Если у старого Location Asset нет сохранённых настроек, существующее поведение обычных MeshPart **без COL** сохраняется до явного Save mesh settings. Для ассетов с COL исправляется неверное назначение Box коллайдеру. Никакой пакетной синхронизации Place установка не выполняет.

### Публикация и Studio

После сохранения настроек **не нужно** перепубликовывать FBX, если геометрия не изменилась: запускается только ручной Sync конкретного slug. Если FBX поменялся, новая публикация Model по-прежнему создаёт новый ID, затем выполняется отдельный Sync. При начальном размещении и при замене управляемого рига используются те же физические опции. Runtime применяет их из сгенерированного `LocationAssetRegistry.luau` после экспорта Host Agent.

Studio Bridge для Location Sync изменён на **schemaVersion 6**. Новый Host Agent должен работать только с установленным M232 Studio-плагином; предыдущий плагин не может принять команду новой версии. Это защита от ложного успешного Sync без новых настроек. Настройки Real Estate M207 по-прежнему управляются её UI и сервисом публикации.

### Приёмка

1. На тестовой копии Place выбрать FBX с `col_mesh`, `window_glass`, `visual` и скелетом. **До Register** проверить, что список и кости появились.
2. Проверить значение `Precise` у `col_mesh`, `Box` и `No Collide` у визуала и стекла при наличии COL. Включить `CanCollide` визуала — fidelity должна стать Precise и заблокироваться.
3. Зарегистрировать, затем открыть `Edit`, убедиться в сохранении выбранных флагов и bone list.
4. Поменять только `No Collide`, нажать `Save mesh settings`: Model Asset ID и SHA FBX не должны измениться. У существующих экземпляров — только после **ручного** `Sync Studio` этого slug.
5. Проверить, что размещения других Location Assets и Real Estate не изменились; проверить `CanQuery`, `CanTouch`, `DoubleSided` у Parts и отсутствие текстуры на COL.

**Не проверено автоматически:** запуск Blender на реальном пользовательском FBX, реальный Studio Edit/Play и визуальная физика в Place. Для них требуется проверка в Roblox Studio. Не запускать массовую синхронизацию без резервной копии Place.

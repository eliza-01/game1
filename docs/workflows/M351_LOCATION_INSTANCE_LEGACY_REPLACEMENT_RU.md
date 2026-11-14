# M351 · Location Instance Manager: исторические Pivot и ручные MeshPart.Size

M351 применяется **поверх M350** и сохраняет проверенный Collision Sync. Действие — `Replace Selected` / `Replace All` в Edit Mode.

Проблема: M347 переносил только Model Scale и старый Model Pivot. Исторические Sync могли менять MeshPart.PivotOffset; ручное изменение Size каждого MeshPart при GetScale()=1 игнорировалось. Простое выравнивание старого и нового Pivot приводило к переносу другой системы координат.

Решение:
- отдельный `StudioLocationInstanceLegacyGeometry` отвечает только за источники трансформаций и перенос Size; Instance Replace остаётся координатором транзакции;
- Preview загружает опубликованную исходную Model по атрибуту опубликованного Model ID, проверяет её реальный Mesh ID, вычисляет применённые к экземпляру ручные коэффициенты Size;
- если PivotOffset старого визуального MeshPart был перебазирован, историческую опору восстанавливаем из геометрического CFrame (не из PivotOffset);
- при Replace к выбранной опоре **новой** Model/MeshPart применяется проверенный старый frame, а ручные Size-коэффициенты переносятся только при строгой привязке локальных осей;
- Collision Blueprint генерируется после Size/CFrame-выравнивания, совместимо с M350; исходные размещения остаются в Undo через Parent=nil;
- несовместимые mesh orientations, multipart или skinned targets с ручным Size не модифицируются, Preview сообщает причину;
- протокол v4 защищает от выполнения команды устаревшим Game1Bridge.

Команда в Asset Manager: **Preview → выбрать Pivot новой Model / нового MeshPart → Replace Selected**. Сначала работать с одним экземпляром. Перед Replace All проверить Ctrl+Z / Ctrl+Y, Collision и фактическую ориентацию в Studio.

Тесты: `test_location_instance*.py`, `test_location_collision*.py`, `test_location_place_registry*.py`, `test_development_kanban_m339.py`, `verify.py`, `validate_luau.py`, `node --check`.

**Не проверено автоматически:** Roblox Studio PivotTo / ScaleTo / ChangeHistoryService в реальной сессии, корректность конкретного target Mesh ID по визуальному виду. Статус **VALIDATING**, только после ручных тестов возможно DONE.

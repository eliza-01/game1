# M264 · Pivot корневой Model при замене опубликованного Location rig

## Причина

При миграции `christmas_tree` старый размещённый Model иногда имел
`PrimaryPart` (например, исторический `col_mesh`). После `Geometry.Align`
новый visual был выровнен по старой геометрии, но `StudioManagedRigSwap`
назначал новый `PrimaryPart` с **другим** импортированным `PivotOffset`.
Roblox при этом переопределял `Model:GetPivot()` по новой детали:
лог показывал `position=6.332645`, `look≈0`, `up≈0`, `scale=1->1`.
Откат был правильным; проблема — не в допуске проверки.

## Исправление

- Shared `StudioManagedRigSwap` перед назначением нового PrimaryPart
  задаёт **только на новом** `BasePart`:
  `newPrimary.PivotOffset = newPrimary.CFrame:ToObjectSpace(placedRootPivot)`.
  Получаем `newPrimary:GetPivot() == placedRootPivot` без `Model:PivotTo`,
  перемещения визуальной геометрии, `col_mesh`, Bone, масштабирования
  или замены самого размещённого Model.
- Когда у размещённого корня **не было** `PrimaryPart`, прежняя ветка
  `Model.WorldPivot` остаётся без изменений. Когда `PrimaryPart` не
  заменяется, он также не корректируется.
- `StudioPublishedMeshHistory.Provenance` доказывает трансформацию
  исторических Mesh ID через `MeshPart.CFrame`, а не `GetPivot()`.
  Это отделяет фактические физические координаты меша от `PivotOffset`:
  последующий Sync не принимает служебную коррекцию pivot за ручное
  перемещение ассета.
- Все прежние guard'ы placed root `parent/pivot/scale`, проверка
  полной исторической иерархии, транзакция/rollback и Studio Undo сохранены.
  При несоответствии source geometry ничего не коммитится.
- Общая механика используется обеими операциями Location Asset Sync,
  Place Registry Sync и Real Estate. Никаких новых Blender/FBX
  конвертеров и синтетических частей.

## Studio smoke на копии Place

1. Для одного старого `christmas_tree` (visual + `col_mesh`) до Sync
   записать `Model:GetPivot`, `GetScale`, `Parent`, `PrimaryPart`,
   `Game1DecoInstanceId`, world `CFrame/Size` старого визуального меша.
2. Выполнить **Find** и **Sync** только для этого экземпляра.
   Ожидаем 1 обновлённую модель, root Instance и все сохранённые параметры
   из шага 1. Новый skinned `rig_carrier` и Bone должны прийти из
   опубликованного FBX, `col_mesh` — сохранить рабочую коллизию.
3. Проверить фактические `CFrame/Size` visual, Bone world-frame,
   ориентацию Model и переключение PrimaryPart. Root не должен повернуться
   или сдвинуться на 6.332645 studs. Проверить Undo и Save/Reopen.
4. Выполнить повторный Find — `pending geometry = 0`; затем проверить
   ещё одну реальную ревизию Model ID, чтобы доказать отсутствие дрейфа
   `StudioPublishedMeshHistory.Provenance` после корректировки PivotOffset.
5. Если один экземпляр не прошёл — не выполнять групповое обновление.

Python-тесты проверяют алгебру компенсации и вызовы общего механизма,
но не заменяют Roblox Studio Edit-mode smoke.

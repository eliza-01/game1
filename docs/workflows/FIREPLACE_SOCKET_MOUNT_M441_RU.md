# M441 · Камин: положение и направление на socket

## Канонический контракт

- Действующий `SocketFacing.Forward`: для `Bone` вперёд = `-TransformedWorldCFrame.UpVector` (Blender **Tail → Head**). Для `Attachment` вперёд = `WorldCFrame.LookVector`.
- `HouseSpawnOrientation.Upright` уже используется в `HouseElevatorService.Move` и `HouseSocketService.TeleportDebug`: проекция forward на мировую XZ, вертикаль всегда мировой +Y. При вертикальном forward нет допустимого направления — действие отклоняется, не придумывается запасной yaw.
- Для персонажа `clearance=3` studs; для размещаемых предметов **`clearance=0`**. Позиция HEAD сокета равна позиции точки монтажа; `GetBoundingBox` не используется.
- Для `firewood_01`, `embers_01`, `cooking_pot_01` точка монтажа берётся из `rig_carrier:GetPivot()` (или `GetPivot()` единственного визуального MeshPart). `BoneModelMount.CreateGrip` и `BoneModelMount.Place` совмещают эту точку и её ориентацию с целевым сокетом. Существующая реализация монтажа оружия/жёстких волос не копируется.
- `cooking_pot_socket` — внутренний сокет модели котла, не сокет House. Пар от него идёт в мировой +Y.

## Ограничения и проверка

`MeshPart` может содержать визуально смещённые вершины относительно своего авторского pivot. Положение geometry/bounds **не является** координатой сокета. Если после точного совмещения grip визуальная геометрия находится ниже, нужно проверить FBX авторский pivot / `rig_carrier` и skinning; нельзя компенсировать ошибку произвольной константой Y или смещением на половину Bounds.

В Studio Play проверить каждый из трёх ассетов на `fireplace_01_socket`: центр grip на HEAD, фасад по Tail → Head, мировой up, отсутствие произвольного vertical offset; проверить flame/steam и оба перехода состояния. Без реального Roblox runtime это не считается подтверждённым.

# M608 · Runtime Socket Bone (KBN-0037-T02)

M607 не прошёл приёмку: у героя волосы и меч отделяются при прыжке, меч охранника не на месте в Idle. У героя в Idle положение корректное. Причина в движке не доказана. Проверяем вариант из https://devforum.roblox.com/t/how-to-use-rigid-constraints-to-add-accessories-to-skinned-meshes/2630017 — constraint на созданной в Roblox дочерней Bone. Официальный API RigidConstraint поддерживает Bone; это не гарантия исправления наблюдаемого бага (см. https://devforum.roblox.com/t/object-attached-to-rigidconstraint-not-sticking-to-a-bone-of-an-animated-skin-mesh/3162276).

Одна Bone `__Game1RigidSocket_<authored name>` с identity CFrame/Transform под исходным сокетом; создаётся при первой экипировке, живёт до удаления рига и переиспользуется. Никаких дополнительных constraints, физических частей, циклов, изменения масс/пивотов/владения root. Bow release вычисляется по исходной кости. Карты анимационной композиции и сравнение NPC-скелетов исключают служебную Bone. Hair readiness проверяет дочернюю Bone и связь joint. Timeline работает по тому же уравнению joint.

## Приёмка (NOT_RUN)

1. Rojo Sync, Studio Play: герой Idle/бег/поворот/прыжок; охранник Idle/бег/атака; оружие/волосы не отделяются. Проверить второго клиента и серверный NPC. Смена оружия и respawn, compound hair, обе руки, bow release, создание/превью персонажа. При смене оружия количество служебных Bones на сокет остаётся 1.
2. Проверить в опубликованном DEV на телефоне, с теми же ассетами; сравнить с M605, измерить Physics/CPU/frame time. Проверить повторно Timeline и стенд. Пересоздать сохранённые до M608 стенды; статический тест не подтверждает работу solver.
3. При повторном дефекте не добавлять follower: зафиксировать состояние joint/родительской и дочерней Bone, client/server ownership и рассмотреть альтернативную нативную архитектуру. Не закрывать KBN-0037-T02 без приёмки.

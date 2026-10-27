# Research notes — подтверждённые сведения и проектные допущения

**Дата просмотра:** 2026-10-26.

## Lineage II

Открытые реализации логики L2 экипировки показывают раздельные `PAPERDOLL_RHAND` / `PAPERDOLL_LHAND` и `SLOT_L_HAND`, но **не содержат данных о bone/socket клиентской скелетной модели**.

- https://github.com/VytautasBoznis/l2.skilas.lt/blob/master/aCis_gameserver/java/net/sf/l2j/gameserver/model/itemcontainer/Inventory.java
- https://github.com/rukhavi/l2j-mobius/blob/master/java/com/l2jserver/gameserver/model/itemcontainer/Inventory.java

**Важное разграничение:** L2 equipment slot для щита и место крепления его игровой геометрии — не одно и то же. Наличие off-hand в инвентаре не доказывает bind к конкретной кости. Для Eyesland мы выбираем **forearm-mounted shield** + независимый hand-mounted weapon, что реализует запрос пользователя, но не претендует на восстановление оригинальной схемы NCsoft.

## Blender — официальный справочник

- Mirror modifier: https://docs.blender.org/manual/en/dev/modeling/modifiers/generate/mirror.html
- Symmetrize bones: https://docs.blender.org/manual/en/5.2/animation/armatures/bones/editing/symmetrize.html
- Weight paint and mirror: https://docs.staging.blender.org/manual/en/latest/sculpt_paint/weight_paint/usage.html
- Normalization/mirror weights: https://docs.staging.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html
- Armature deform: https://docs.staging.blender.org/manual/en/latest/animation/armatures/skinning/parenting.html
- Blender's MCP server: https://www.blender.org/lab/mcp-server/ — доступен начиная с Blender 5.1, подключается отдельно, нет LLM-соединения «из коробки». Не путать с community implementation.
- Community implementation: https://github.com/ahujasid/mcp-for-blender — альтернативная реализация Blender MCP.

## Roblox — только фактический импорт custom skinned rigs

- https://create.roblox.com/docs/studio/importer — параметр `Rig Type: Custom` поддерживается; поддержка FBX/glTF зависит от импортёра и настроек.
- https://create.roblox.com/docs/art/modeling/rigging — скелеты/skin и bone data в собственных 3D моделях.
- https://create.roblox.com/docs/art/modeling/specifications — общие физические ограничения импортируемых мешей; max 4 bone weights per vertex, no root skin influence; note Roblox export/import constraints but not Roblox avatar layouts.

**Почему важно:** это полностью кастомный персонаж, но Blender-проект не должен разрабатываться так, чтобы потом гарантированно ломаться при игровом импорте. Настоящий импорт в Roblox Studio требуется проверить пользователю/в игровом пайплайне отдельно.

## Самостоятельные решения Eyesland, не «факты про Lineage II»

33 кости и 15 регионов, `shield_mount` parent=`forearm`, собственные `.L/.R` идентификаторы, общая bind pose, A-pose, budgets и threshold QA, seam rings и coverage mapping — разработанный для Eyesland контракт. Они намеренно не копируют имена или внутренние файлы оригинального Lineage II.

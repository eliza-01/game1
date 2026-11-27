# M607 · Native Rigid Equipment (KBN-0037-T02)

Существующие FBX, Model ID, атласы и grip/pivot не меняются. Сервер один раз выравнивает предмет по канонической Bone с прежней коррекцией -90° X для оружия / SocketFacing для волос. Constraint связывает Bone и offset attachment; составные MeshPart соединяются WeldConstraint. Massless, CanCollide/CanTouch/CanQuery=false, низкий RootPriority. Деформируемые части тела используют прежний skinning. Игроки и NPC используют WeaponEquipService; rigid hair создаётся CharacterAssemblyBuilder. Старый BoneMountedAttachmentController удалён. Character Creation клонирует готовый joint и освобождает только оборудование, тело превью остаётся anchored. Studio Timeline WorldModel применяет точное уравнение joint при явном семплировании; никаких runtime fallback. Bow release вычисляется относительно анимированной кости.

## Приёмка (NOT_RUN)

1. Установить M607 поверх M606a; обновить Studio plugin, Rojo Sync. Проверить мужской и женский риг, compound hair и смену цветов/причёсок в Character Creation, вращение превью, Timeline scrub. Пересоздать старые авторские Character Test Stands, которые были сохранены в Place до M607: у старых моделей нет нативных joint. Новый стенд закреплён в Edit и освобождает только экипировку при Studio Play.
2. Проверить бег, резкие развороты, прыжок, атаку, смерть/respawn, смену dagger/sword/bigsword/bow и dualswords. Проверить NPC обеих рук, два клиента и отсутствие изменения коллизий/владения навигационным root. Оружие не должно вращать/тянуть персонажа.
3. Опубликовать DEV Runtime обычным процессом. На физическом Android проверить отставание волос и оружия, FPS/CPU/GPU/Physics/frame time/RAM в одинаковой сцене M605/M607. Не принимать по эмуляции PC.
4. Проверить bow release и hit/aim parity, отсутствие старого follower и лишних соединений. Если нативный joint не следует за animated bone, не возвращать frame loop автоматически: зафиксировать дефект и выбрать решение с владельцем. Откат — обратный патч и пересборка Runtime (DataStore не изменяется).

Профилирование ещё открыто; уменьшение Luau-операций не доказывает уменьшение общего frame time.

"""Source-backed shared NPC mechanics cards; never imply per-slug inspection."""
from .house import card

ITEMS = [
    card('npc-spawn-lifecycle', 'NPC · размещение, смерть и повторное появление', 'Сервер',
         'Авторские spawn-record и опубликованные шаблоны; живые NPC принадлежат одному серверу.',
         ['NpcSpawnRegistry.records', 'NpcRegistry.npcs'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'NpcSpawnerService читает опубликованный NpcRegistry, создаёт риг на авторской позиции, подключает hitbox, анимацию и вооружение.',
                 'После смерти проходит death/DeathIdle, освобождение ресурсов и отложенное повторное появление; leash-пересоздание не использует таймер смерти.',
                 'Spawn registry сохраняется как авторский манифест проекта, а не как игровое состояние текущего сервера.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Нет DataStore-восстановления HP, текущего положения, смерти, оставшегося respawn-delay и состояния отдельного NPC между серверами.',
                 'Протестировать опубликованный Runtime Place, StreamingEnabled, позднее появление ServerStorage-шаблонов и cleanup после смерти/пересоздания.',
                 'Индивидуальные скрипты каждого NPC не зарегистрированы в Mechanics: эта карта описывает только общий runtime; audit конкретного slug требует отдельной карточки.',
             ]},
         ], ['npc-spawner', 'npc-spawns', 'npc-registry', 'npc-death']),
    card('npc-combat-home', 'NPC · агрессия, погоня, возврат', 'Сервер',
         'Серверная проверка цели и дистанции, общий навигатор и радиус от spawn.',
         ['NpcHomeRadiusStuds', 'NpcTargetUserId'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'M615: периодические решения NPC через общий ActorAIScheduler (0,1 с с сохранением общей фазы). Heartbeat движения во время атаки и обработка урона сохраняются. AI LOD не включён.',
                 'M616: общий ActorCombatTargeting.ClosestPlayer использует XZ spatial index, но NPC остаются retaliation-only; новый автоматический Aggro не включён.',
                 'NpcCombatAIService обрабатывает ответный бой, навигацию, атаку, DamageService и возврат домой; policy общих акторов вынесены в actor-модули.',
                 'M614: серверные melee, bow и headshot выбирают кандидатов через GetPartBoundsInBox по существующим RootCollider; точные bone-local hitboxes и дистанция луча сохранены. Studio/DEV и нагрузочная приёмка открыты.',
                 'NPC leash задаётся для spawn-record; общий таймаут без успешного урона берётся из GameOptions.HostileNoDamageReturnSeconds().',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Агрессия, target, Return, attack progress и lastDamageAt не записываются в постоянный player/world store — при рестарте пересоздаются.',
                 'Нужна игровая проверка при прерывании атаки, новом уроне во время Return, переходах через Terrain/этажи и многопользовательской угрозе.',
             ]},
         ], ['npc-ai', 'actor-ai-scheduler', 'actor-ai-queue', 'player-spatial-index', 'player-spatial-grid', 'actor-target-root', 'actor-home', 'actor-nav', 'damage-service', 'npc-policy', 'entity-hitbox', 'native-spatial-index']),
    card('npc-visual-equipment', 'NPC · анимации, оружие, надголовный UI', 'Презентация',
         'Боевые решения и визуальная анимация разделены; предметы берутся из авторского loadout.',
         ['NpcEquipmentRegistry.loadouts', 'NpcAnimationRegistry.profiles'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'NpcAnimationService владеет animation tracks, NpcEquipmentService монтирует оружие через общий WeaponEquipService. M613: общий пул NPC/Monster ограничен 32 экземплярами, включая idle и резерв загрузки; lifecycle и повторное использование централизованы.',
                 'NpcOverheadController отображает имя и условный HP в радиусах Options. HealthBarView удаляет цифры только из отображаемого имени NPC; slug, имя Instance, база и уровень не изменяются.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Опубликованный loadout не является персональным инвентарём NPC; временная смена экипировки и анимационной фазы не восстанавливается из DataStore.',
                 'Нужна Studio/мобильная и мультиклиентская проверка оружия, клипов, HP-видимости, стриминга и очистки GUI.',
             ]},
         ], ['npc-animation', 'npc-equipment', 'npc-animation-registry', 'npc-overhead', 'npc-display-name', 'weapon-equip']),
]

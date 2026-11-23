"""Shared player mechanics and current persistence gaps; source-grounded."""
from .house import card

ITEMS = [
    card('character-assembly-spawn', 'Персонаж · сборка и появление', 'Сервер',
         'Выбор опубликованного archetype, сборка кастомного rig и runtime stats.',
         ['CharacterRegistry.archetypes', 'CharacterStatsService'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'CharacterService создаёт авторскую модель и выставляет runtime attributes для skeleton, stats, движения и анимаций.',
                 'SelectedCharacterArchetype хранится как атрибут Player текущей сессии; authoring registry — не данные пользователя.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Нет подтверждённого DataStore-профиля игрока для выбранного персонажа, его HP/характеристик, позиции и долговременной прогрессии.',
                 'Нужна Studio и published server проверка ошибок загрузки, R15/Humanoid compatibility, скелета, входа второго игрока и повторного спавна.',
             ]},
         ], ['character-service', 'character-stats', 'character-registry', 'character-rig']),
    card('character-movement-camera', 'Персонаж · движение, камера, touch', 'Управление',
         'Кастомный ControllerManager, ПКМ и touch/мобильные действия.',
         ['CharacterMovementConfig', 'MobileLayout'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'MovementController, CameraController и MobileInputController управляют локальным вводом; HouseCameraSync согласует heading после телепорта.',
                 'Управление на PC и Touch не должно требовать Studio Debug или Control Center при публикации.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Текущая камера, ввод и позиция не являются persistent profile; сохранённые Options — настройки проекта, а не предпочтения конкретного игрока.',
                 'Обязательная приёмка ПКМ/поворота камеры, pinch/drag, боевого управления, безопасных областей телефонов и изменения viewport.',
             ]},
         ], ['movement-client', 'camera-client', 'mobile-client', 'camera-sync', 'movement-config']),
    card('character-weapon-attack', 'Персонаж · оружие, melee и bow', 'Бой',
         'Серверная проверка атак, отдельный hitscan лука и визуальная стрела.',
         ['AttackService', 'BowHitscanService', 'WeaponEquipService'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'AttackService/AttackDamageResolver подтверждают melee-контакт, DamageService применяет урон, BowHitscanService делает серверный мгновенный контакт.',
                 'Выбранное оружие монтируется через BoneModelMount, а летящая/застрявшая стрела — клиентская визуализация, не второй серверный снаряд.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'WeaponSelectionService — игровой playtest chooser; нет доказанной persistent ownership/inventory модели для выбранного предмета.',
                 'Отдельно проверить урон при тесном контакте, прицеливание вверх/вниз, разные MeshPart, mobile auto-aim, lag/повторный Release и права игрока.',
             ]},
         ], ['attack-service', 'bow-hitscan', 'damage-service', 'weapon-equip', 'weapon-select', 'bone-mount']),
    card('character-death-respawn', 'Персонаж · HP, смерть, Return to Town', 'Сервер',
         'HP и LifeState контролирует сервер; после смерти персонаж ожидает Return to Town.',
         ['LifeState', 'ReturnToTownAvailable'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'CharacterService запускает DeathIdle без автоматического respawn и создаёт нового персонажа по ReturnToTown после серверной проверки состояния.',
                 'CharacterRegenerationService обновляет восстановление; DamageService работает с серверными HP/Defense и LifeState.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'HP, смерть, cooldown восстановления, checkpoint и возвращение в город не сохраняются как аккаунтная прогрессия между сессиями.',
                 'Нужна мультиклиентская проверка death/return, повторных команд, гонок респавна и очистки старого hitbox/animation/UI.',
             ]},
         ], ['character-service', 'character-regeneration', 'death-service', 'damage-service']),
    card('character-visual-ui', 'Персонаж · анимации, UI и уведомления', 'Презентация',
         'Клиентские анимации, оборудование, полосы здоровья, UI-профили и уведомления ресурсов.',
         ['GameOptions.UiPresentationSettings', 'InformativeWindowDock'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'CharacterAnimationController и BoneMountedAttachmentController отвечают за клипы и следование креплений.',
                 'InformativeWindowDock управляет сворачиванием информационных окон; FloatingResourceFeedback отображает +N/−N над головой.',
                 'Options → UI сохраняет desktop/mobile profile в manifest и генерируемый GameOptionsRegistry; Studio Debug остаётся локальным предпросмотром.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Свёрнутость окна и живой Studio preview — временное клиентское состояние. Нет персональной синхронизации UI-предпочтений/уведомлений в DataStore.',
                 'Визуальный +N/−N сам по себе не доказывает изменение серверного inventory; отсутствует общий authoritative ledger для ресурсов/награды.',
                 'Обязательно проверить в реальном Play и на телефоне: шевроны, ПКМ, safe area, respawn/head Bone, мультиклиент и LOD/Streaming.',
             ]},
         ], ['character-animation', 'bone-client', 'info-dock', 'resource-feedback', 'ui-settings', 'health-ui']),
]

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
                 'DataStore хранит до 5 независимых персонажей: внешний вид, XP, Gold и последняя позиция. HP/временные характеристики не сохраняются. Published DEV требует отдельной приёмки миграции.',
                 'Нужна Studio и published server проверка ошибок загрузки, R15/Humanoid compatibility, скелета, входа второго игрока и повторного спавна.',
             ]},
         ], ['character-service', 'character-stats', 'character-registry', 'character-rig']),
    card('character-roster', 'Персонаж · выбор, создание и удаление', 'Сервер + UI',
         'M596: до пяти независимых персонажей аккаунта, миграция существующего слота без сброса прогресса.',
         ['CharacterCreation', 'CharacterProfileRoster', 'DataStore UpdateAsync'], [
             {'title': 'Контракт', 'lines': [
                 'Новый персонаж открывает редактор; стрелки переключают сохранённые слоты. Удаление только на экране выбора после подтверждения; удаляется только выбранный ID.',
                 'У каждого ID собственные appearance, XP, Gold и lastWorldCFrame. Общий язык и палитра аккаунта сохраняются. Удаление последнего персонажа возвращает в создание.',
                 'Хранилище schema v2 в прежнем ключе аккаунта; v1 переносится в первый слот. UpdateAsync проверяет ревизию, предотвращая устаревшую перезапись; при конфликте требуется переподключение.',
                 'Перед публикацией остановить все старые серверы Experience, поскольку v1 не умеет защищать v2. Не откатывать сервер на v1 после миграции.',
             ]},
             {'title': 'Приёмка', 'lines': [
                 'Проверить PC/Mobile в DEV: миграция, создание до лимита, переключение персонажей одного пола, отказ/подтверждение удаления, удаление последнего, независимость прогресса и повторный вход.',
                 'Создание и удаление используют серверный ID, этап и лимит; не требуют Debug. При недоступном DataStore published не меняет профили.',
             ]},
         ], ['character-creation-gateway', 'character-roster-gateway', 'character-profile-store', 'character-profile-roster', 'character-roster-view']),
    card('character-movement-camera', 'Персонаж · движение, камера, touch', 'Управление',
         'Кастомный ControllerManager, ПКМ и touch/мобильные действия.',
         ['CharacterMovementConfig', 'MobileLayout'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'MovementController, CameraController и MobileInputController управляют локальным вводом; HouseCameraSync согласует heading после телепорта.',
                 'M597: удержание ЛКМ/Attack повторяет атаку по timeline, Jump повторяется после приземления. Action touches поворачивают камеру; отдельный свободный палец имеет приоритет. Зелёная кнопка — toggle автоатаки, оранжевые — резерв skills.',
                 'M598: MobileLayout задаёт общий масштаб: Attack у нижнего правого угла, Jump/Auto/Skills около 46% его диаметра; 4 Skills по дуге вокруг Attack, weapon slots около 37% вверху справа. Context/info dock учитывает реальные границы. HudCornerLayout резервирует 44 px для Settings, Debug сдвинут вправо и не занимает weapon grid. WalletHud подгоняет ширину по Gold.',
                 'M599: Touch Debug — только GP (Studio), UI presentation, HP и CD; оружейные слоты экипируют тип напрямую через DEV RPC без окна каталога. Desktop без изменений.',
                 'M605: Attack / Skill 4 / weapon grid имеют общий DeviceSafeInsets right=2 px; Jump на одной вертикали со Skill 1, единый фон Wallet, SVG Attack/Jump/Aim.',
                 'M602: S/Down и нижняя половина touch-стика включают Walk/Backward относительно текущего yaw камеры без ПКМ и без атаки; analog strength/diagonals на touch сохранены. Боевые facing/movement locks сохраняют приоритет.',
                 'M601: weapon grid 2 px от верхнего/правого края DeviceSafeInsets, размер рассчитывается по CoreUISafeInsets (37% Attack). Newbie Slayer 01 связан с Database weapon_003 (bigsword LVL 1); пустая категория диагностируется и повторно запрашивает каталог при следующем выборе.',
                 'Управление на PC и Touch не должно требовать Studio Debug или Control Center при публикации.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Текущая камера, ввод и позиция не являются persistent profile; сохранённые Options — настройки проекта, а не предпочтения конкретного игрока.',
                 'Обязательная приёмка ПКМ/поворота камеры, pinch/drag, боевого управления, безопасных областей телефонов и изменения viewport.',
             ]},
         ], ['movement-client', 'camera-client', 'mobile-client', 'mobile-actions', 'mobile-layout', 'hud-corner-layout', 'attack-repeat', 'mobile-weapon-slots', 'mobile-weapon-quick-select', 'weapon-slot-catalog', 'debug-dock-profile', 'camera-sync', 'movement-config']),
    card('character-weapon-attack', 'Персонаж · оружие, melee и bow', 'Бой',
         'Серверная проверка атак, отдельный hitscan лука и визуальная стрела.',
         ['AttackService', 'BowHitscanService', 'WeaponEquipService'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'AttackService/AttackDamageResolver подтверждают melee-контакт, DamageService применяет урон, BowHitscanService делает серверный мгновенный контакт.',
                 'M612: принятое сервером состояние атаки реплицируется наблюдателям; общий upper-body composer воспроизводит опубликованный клип поверх native locomotion. Studio/DEV-приёмка открыта.',
                 'M609: выбранное оружие и NPC используют общий RigidEquipmentMount на родительской Bone с authored offset (один RigidConstraint на предмет), а летящая/застрявшая стрела — клиентская визуализация, не второй серверный снаряд.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'WeaponSelectionService — playtest chooser: Studio или точный DEV Place ID из Options → Debug / TestPlace (включая compiled Runtime), при включённых галочках PC/Mobile; все допущенные тестировщики. Нет доказанной persistent ownership/inventory модели для выбранного предмета.',
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
                 'CharacterAnimationController отвечает за клипы; M609: волосы и оружие используют RigidConstraint на родительской Bone с authored offset (владелец подтвердил Runtime и телефон), без клиентского follower. Полная регрессия и сравнительные замеры CPU/Physics ещё открыты.',
                 'M605: при входе в мир curtain ожидает текущий track cache и однократный клиентский preload опубликованных NPC/Monster клипов (общий лимит ожидания 12 с). При отключённом Character Creation прогрев фоновый. Death немедленно прекращает композицию нижней части тела.',
                 'InformativeWindowDock управляет сворачиванием информационных окон; FloatingResourceFeedback отображает +N/−N над головой.',
                 'Options → UI сохраняет desktop/mobile profile в manifest и генерируемый GameOptionsRegistry; Studio Debug остаётся локальным предпросмотром.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Свёрнутость окна и живой Studio preview — временное клиентское состояние. Нет персональной синхронизации UI-предпочтений/уведомлений в DataStore.',
                 'Визуальный +N/−N сам по себе не доказывает изменение серверного inventory; отсутствует общий authoritative ledger для ресурсов/награды.',
                 'Обязательно проверить в реальном Play и на телефоне: шевроны, ПКМ, safe area, respawn/head Bone, мультиклиент и LOD/Streaming.',
             ]},
         ], ['character-animation', 'world-animation-preload', 'bone-mount', 'info-dock', 'resource-feedback', 'ui-settings', 'health-ui']),
]

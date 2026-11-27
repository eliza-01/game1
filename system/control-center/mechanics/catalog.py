"""One mechanics documentation schema for shared rules and future per-asset scripts."""
from .house import ITEMS as HOUSE_ITEMS
from .windmill import ITEMS as WINDMILL_ITEMS
from .npc import ITEMS as NPC_ITEMS
from .monster import ITEMS as MONSTER_ITEMS
from .character import ITEMS as CHARACTER_ITEMS

DOMAINS = (
    {'id': 'house', 'label': 'House', 'description': 'Сокеты, взаимодействия и правила домов', 'items': HOUSE_ITEMS},
    {'id': 'windmill', 'label': 'Windmill', 'description': 'Windmill 02 · ротор и дверь', 'items': WINDMILL_ITEMS},
    {'id': 'npc', 'label': 'NPC', 'description': 'Технические карты по каждому NPC и его собственным скриптам', 'items': NPC_ITEMS},
    {'id': 'monster', 'label': 'Monster', 'description': 'Общие серверные механики монстров: spawn, AI, навигация, бой и возврат', 'items': MONSTER_ITEMS},
    {'id': 'character', 'label': 'Character', 'description': 'Механики персонажа и общий контракт управления', 'items': CHARACTER_ITEMS},
)

# Keys are the only legal way to read source text through this API. Future
# actor-specific scripts belong to a distinct item's sources list, never an
# arbitrary file path supplied by the browser.
SOURCES = {
    'npc-spawner': ('src/server/npc/NpcSpawnerService.luau', 'NPC · spawn и lifecycle'),
    'npc-spawns': ('src/server/npc/NpcSpawnRegistry.luau', 'NPC · записи spawn'),
    'npc-registry': ('src/shared/npc/NpcRegistry.luau', 'NPC · опубликованный реестр'),
    'npc-death': ('src/server/combat/DeathLifecycleService.luau', 'Общий death lifecycle'),
    'npc-ai': ('src/server/npc/NpcCombatAIService.luau', 'NPC · боевой AI'),
    'actor-home': ('src/server/actor/ActorHomeLeash.luau', 'Общий leash'),
    'actor-nav': ('src/server/actor/ActorChaseNavigator.luau', 'Навигация акторов'),
    'damage-service': ('src/server/combat/DamageService.luau', 'Серверный урон'),
    'npc-policy': ('src/shared/npc/NpcMovementPolicy.luau', 'NPC · движение'),
    'npc-animation': ('src/server/npc/NpcAnimationService.luau', 'NPC · анимации'),
    'npc-equipment': ('src/server/npc/NpcEquipmentService.luau', 'NPC · экипировка'),
    'npc-animation-registry': ('src/shared/npc/NpcAnimationRegistry.luau', 'NPC · клипы'),
    'npc-display-name': ('src/client/combat/NpcDisplayNameFormatter.luau', 'NPC · форматирование имени'),
    'door-mesh-aim': ('src/client/world/DoorInteractionRaycast.luau', 'House · наведение на меш двери'),
    'house-state-icons': ('src/client/HudSvgIcons.luau', 'House · SVG-иконки состояний'),
    'npc-overhead': ('src/client/combat/NpcOverheadController.luau', 'NPC · имя и здоровье'),
    'weapon-equip': ('src/server/weapon/WeaponEquipService.luau', 'Оружие · монтаж'),
    'monster-spawner': ('src/server/monster/MonsterSpawnerService.luau', 'Monster · spawn'),
    'monster-population': ('src/server/monster/MonsterPopulationController.luau', 'Monster · слоты и respawn'),
    'monster-death': ('src/server/monster/MonsterDeathLifecycle.luau', 'Monster · смерть'),
    'monster-spawns': ('src/server/monster/MonsterSpawnRegistry.luau', 'Monster · записи spawn'),
    'monster-registry': ('src/shared/monster/MonsterRegistry.luau', 'Monster · типы'),
    'monster-ai': ('src/server/monster/MonsterAIService.luau', 'Monster · AI'),
    'monster-target': ('src/server/monster/MonsterTargetPolicy.luau', 'Monster · приоритет цели'),
    'monster-nav': ('src/server/monster/MonsterChaseNavigation.luau', 'Monster · Legacy навигация'),
    'monster-death-chase': ('src/server/monster/MonsterDeathChasePolicy.luau', 'Monster · Home Leash / Death Chase'),
    'monster-nav-dispatch': ('src/server/monster/MonsterNavigationDispatch.luau', 'Monster · выбор backend'),
    'monster-nav-experimental': ('src/server/monster/MonsterExperimentalNavigation.luau', 'Monster · Experimental Navigation'),
    'monster-nav-config': ('src/server/monster/MonsterNavigationConfig.luau', 'Monster · конфигурация навигации'),
    'monster-nav-options': ('src/shared/GameOptionsRegistry.luau', 'Options · значения навигации'),
    'monster-recovery-geometry': ('src/server/monster/MonsterRecoveryGeometry.luau', 'Monster · лучи и обход'),
    'monster-climb': ('src/server/monster/MonsterClimbMotion.luau', 'Monster · прыжок и таймаут'),
    'monster-rescue-graph': ('src/server/monster/MonsterRescueGraph.luau', 'Monster · Rescue Route graph'),
    'monster-rescue-topology': ('src/server/monster/MonsterRescueTopology.luau', 'Monster · Rescue Route topology'),
    'monster-rescue-segments': ('src/server/monster/MonsterRescueSegments.luau', 'Monster · Rescue Route segment geometry'),
    'monster-rescue-routes': ('src/server/monster/MonsterRescueRoutes.luau', 'Monster · Rescue Route route ranking'),
    'monster-rescue-connections': ('src/server/monster/MonsterRescueConnections.luau', 'Monster · Rescue Route transitions'),
    'monster-rescue-sampling': ('src/server/monster/MonsterRescueSampling.luau', 'Monster · Rescue Route sampling 20/4'),
    'monster-rescue-entries': ('src/server/monster/MonsterRescueEntries.luau', 'Monster · Rescue Route entry search'),
    'monster-rescue-exits': ('src/server/monster/MonsterRescueExits.luau', 'Monster · Rescue Route exit selection'),
    'monster-rescue-paths': ('src/server/monster/MonsterRescuePaths.luau', 'Monster · Rescue Route path search'),
    'monster-rescue-queries': ('src/server/monster/MonsterRescueQueries.luau', 'Monster · Rescue Route query cache'),
    'monster-blocked-pursuit': ('src/server/monster/MonsterBlockedPursuit.luau', 'Monster · политика отступления и ожидания'),
    'monster-blocked-retreat-geometry': ('src/server/monster/MonsterBlockedRetreatGeometry.luau', 'Monster · геометрия отступления'),
    'monster-navigation-speed': ('src/server/monster/MonsterNavigationSpeed.luau', 'Monster · множители скорости навигации'),
    'monster-stuck-watchdog': ('src/server/monster/MonsterStuckWatchdog.luau', 'Monster · watchdog прогресса'),
    'monster-home-recall': ('src/server/monster/MonsterHomeRecall.luau', 'Monster · аварийный телепорт домой'),
    'monster-home-recall-visuals': ('src/client/monster/MonsterHomeRecallVisuals.luau', 'Monster · эффект телепорта'),
    'monster-buff-visuals': ('src/client/combat/BuffCastVisuals.luau', 'Общий эффект бафа'),
    'monster-nav-trace': ('src/server/monster/MonsterNavigationTrace.luau', 'Monster · диагностика MONNAV'),
    'monster-gameplay-doc': ('docs/workflows/M570_GAMEPLAY_INFRASTRUCTURE_RU.md', 'Gameplay · актуальная карта M582'),
    'monster-attack': ('src/server/monster/MonsterAttackExecutor.luau', 'Monster · атака'),
    'monster-client-attack': ('src/client/monster/MonsterAttackLocomotionController.luau', 'Monster · клиентская анимация'),
    'entity-hitbox': ('src/server/combat/EntityHitboxService.luau', 'Hitbox · авторитет сервера'),
    'actor-ai-scheduler': ('src/server/actor/ActorAIScheduler.luau', 'Actor · AI scheduler'),
    'actor-ai-queue': ('src/server/actor/ActorAIScheduleQueue.luau', 'Actor · AI deadline queue'),
    'native-spatial-index': ('src/shared/world/NativePartSpatialIndex.luau', 'Spatial Index · native broad phase'),
    'character-service': ('src/server/character/CharacterService.luau', 'Персонаж · жизненный цикл'),
    'character-creation-gateway': ('src/server/character/CharacterCreationGateway.luau', 'Создание и вход в мир'),
    'character-roster-gateway': ('src/server/character/CharacterRosterGateway.luau', 'Управление слотами'),
    'character-profile-store': ('src/server/character/CharacterCreationProfileStore.luau', 'Хранилище аккаунта'),
    'character-profile-roster': ('src/server/character/CharacterProfileRoster.luau', 'Схема и миграция'),
    'character-roster-view': ('src/client/character/CharacterRosterView.luau', 'Выбор персонажа · UI'),
    'character-stats': ('src/server/character/CharacterStatsService.luau', 'Статистика'),
    'character-registry': ('src/shared/character/CharacterRegistry.luau', 'Персонажи · реестр'),
    'character-rig': ('src/server/character/CharacterRigService.luau', 'Сборка рига'),
    'movement-client': ('src/client/character/MovementController.luau', 'Движение · клиент'),
    'camera-client': ('src/client/character/CameraController.luau', 'Камера · клиент'),
    'mobile-client': ('src/client/character/MobileInputController.luau', 'Мобильное управление'),
    'mobile-actions': ('src/client/character/mobile/MobileActionTouches.luau', 'Состояние action touches'),
    'hud-corner-layout': ('src/client/HudCornerLayout.luau', 'Общая геометрия Settings / Debug'),
    'mobile-layout': ('src/client/character/mobile/MobileLayout.luau', 'Мобильная safe-area геометрия'),
    'attack-repeat': ('src/client/combat/AttackRepeatInput.luau', 'Удержание атаки'),
    'debug-dock-profile': ('src/client/dev/DebugDockProfile.luau', 'Набор Debug по устройству'),
    'mobile-weapon-quick-select': ('src/client/weapon/MobileWeaponQuickSelect.luau', 'Переключение оружия без меню'),
    'weapon-slot-catalog': ('src/client/weapon/WeaponSlotCatalog.luau', 'Выбор доступного slug'),
    'mobile-weapon-slots': ('src/client/weapon/MobileWeaponSlots.luau', 'Четыре DEV ячейки оружия'),
    'movement-config': ('src/shared/character/CharacterMovementConfig.luau', 'Параметры движения'),
    'attack-service': ('src/server/combat/AttackService.luau', 'Melee · сервер'),
    'bow-hitscan': ('src/server/combat/BowHitscanService.luau', 'Bow · серверный hitscan'),
    'weapon-select': ('src/server/weapon/WeaponSelectionService.luau', 'Выбор оружия в Play'),
    'bone-mount': ('src/shared/rig/RigidEquipmentMount.luau', 'Нативное крепление экипировки'),
    'character-regeneration': ('src/server/character/CharacterRegenerationService.luau', 'HP regeneration'),
    'death-service': ('src/server/combat/DeathLifecycleService.luau', 'Death lifecycle'),
    'world-animation-preload': ('src/client/character/animation/WorldAnimationPreloader.luau', 'Прогрев анимаций мира'),
    'character-animation': ('src/client/character/animation/CharacterAnimationController.luau', 'Анимации персонажа'),
    'info-dock': ('src/client/world/InformativeWindowDock.luau', 'Информативные окна'),
    'resource-feedback': ('src/client/world/FloatingResourceFeedback.luau', 'Получение и расход'),
    'ui-settings': ('src/client/world/UiPresentationSettings.luau', 'UI-профили'),
    'health-ui': ('src/client/combat/PlayerHealthHudController.luau', 'HP-интерфейс'),
    'windmill-rotation-client': ('src/client/world/WindmillRotorVisual.luau', 'Ротор · blades + fabric'),
    'windmill-door-client': ('src/client/world/WindmillDoorVisual.luau', 'Дверь · Bone.Transform'),
    'windmill-observer-client': ('src/client/world/WindmillVisualController.luau', 'Клиент · жизненный цикл'),
    'windmill-door-server': ('src/server/world/WindmillDoorService.luau', 'Сервер · валидация и состояние'),
    'windmill-options': ('src/shared/GameOptionsRegistry.luau', 'Options · rotations'),
    'windmill-doc': ('docs/workflows/WINDMILL_02_MECHANICS_M452_RU.md', 'Мельница · авторинг и ограничения'),
    'socket-contract': ('src/shared/world/HouseSocketContract.luau', 'Контракт сокетов'),
    'socket-service': ('src/server/world/HouseSocketService.luau', 'Реестр и валидация'),
    'socket-discovery': ('src/server/world/HouseSocketDiscovery.luau', 'Обнаружение домов'),
    'socket-prompt': ('src/client/world/HouseSocketPromptController.luau', 'Клиентский UI'),
    'socket-aim': ('src/shared/world/HouseSocketAimPolicy.luau', 'Наведение'),
    'socket-occlusion': ('src/client/world/HouseSocketAimOcclusion.luau', 'Проверка видимости'),
    'door-service': ('src/server/world/HouseDoorService.luau', 'Дверь'),
    'padlock-service': ('src/server/world/HousePadlockService.luau', 'Замок'),
    'padlock-visuals': ('src/server/world/HousePadlockVisuals.luau', 'Замок · две стороны'),
    'elevator-service': ('src/server/world/HouseElevatorService.luau', 'Лифт'),
    'elevator-policy': ('src/shared/world/HouseElevatorPolicy.luau', 'Маршрутизация этажей'),
    'spawn-orientation': ('src/shared/world/HouseSpawnOrientation.luau', 'Направление spawn'),
    'camera-sync': ('src/server/character/CharacterCameraSync.luau', 'Синхронизация камеры'),
    'socket-effects': ('src/server/world/HouseSocketEffects.luau', 'Эффекты/заглушки'),
    'fireplace-service': ('src/server/world/HouseFireplaceService.luau', 'Камин и готовка'),
    'fireplace-mount': ('src/server/world/HouseSocketAssetMount.luau', 'Монтаж и Appearance'),
    'campfire-service': ('src/server/world/LocationCampfireService.luau', 'Костры · размещения и доступ'),
    'campfire-socket-contract': ('src/shared/world/CampfireSocketContract.luau', 'Костёр · отдельный USE/AIM контракт'),
    'socket-debug-server': ('src/server/dev/HouseSocketDebugService.luau', 'House + Campfire Studio Debug · сервер'),
    'socket-debug-client': ('src/client/dev/HouseSocketDebugController.luau', 'House + Campfire Studio Debug · клиент'),
    'fireplace-config': ('src/shared/world/FireplaceMechanicsConfig.luau', 'Огонь, ресурсы и таймеры'),
    'fireplace-tuning': ('src/shared/world/FireplaceMechanicsTuning.luau', 'Генерируемые параметры'),
    'fireplace-status': ('src/client/world/HouseFireplaceController.luau', 'Индикаторы огня и готовки'),
    'informative-window-dock': ('src/client/world/InformativeWindowDock.luau', 'Общий интерфейс информативных окон'),
    'fireplace-doc': ('docs/workflows/CAMPFIRE_AND_FIREPLACE_M442_RU.md', 'Камин и костёр · M442'),
    'socket-authoring-doc': ('docs/workflows/REAL_ESTATE_SOCKET_AND_PLOT_PIVOT_M373_RU.md', 'Канонические сокеты · M373'),
    'socket-ownership-doc': ('docs/workflows/REAL_ESTATE_SHARED_RIG_SOCKET_OWNERSHIP_M182_RU.md', 'Владение костями · M182'),
    'teleport-camera-doc': ('docs/workflows/HOUSE_TELEPORT_CAMERA_M431_RU.md', 'Камера после телепорта · M431'),
}


def snapshot():
    return {
        'version': 1,
        'domains': [
            {'id': d['id'], 'label': d['label'], 'description': d['description'],
             'items': [dict(item, sources=[
                 {'id': key, 'title': SOURCES[key][1], 'path': SOURCES[key][0]}
                 for key in item['sources']]) for item in d['items']]}
            for d in DOMAINS
        ],
    }


def permitted_source(item_id: str, source_id: str):
    for domain in DOMAINS:
        for item in domain['items']:
            if item['id'] == item_id and source_id in item['sources']:
                return SOURCES[source_id]
    return None

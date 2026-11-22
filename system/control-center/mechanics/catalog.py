"""One mechanics documentation schema for shared rules and future per-asset scripts."""
from .house import ITEMS as HOUSE_ITEMS

DOMAINS = (
    {'id': 'house', 'label': 'House', 'description': 'Сокеты, взаимодействия и правила домов', 'items': HOUSE_ITEMS},
    {'id': 'npc', 'label': 'NPC', 'description': 'Технические карты по каждому NPC и его собственным скриптам', 'items': []},
    {'id': 'monster', 'label': 'Monster', 'description': 'Технические карты по каждому монстру и его собственным скриптам', 'items': []},
    {'id': 'character', 'label': 'Character', 'description': 'Механики персонажа и общий контракт управления', 'items': []},
)

# Keys are the only legal way to read source text through this API. Future
# actor-specific scripts belong to a distinct item's sources list, never an
# arbitrary file path supplied by the browser.
SOURCES = {
    'socket-contract': ('src/shared/world/HouseSocketContract.luau', 'Контракт сокетов'),
    'socket-service': ('src/server/world/HouseSocketService.luau', 'Реестр и валидация'),
    'socket-discovery': ('src/server/world/HouseSocketDiscovery.luau', 'Обнаружение домов'),
    'socket-prompt': ('src/client/world/HouseSocketPromptController.luau', 'Клиентский UI'),
    'socket-aim': ('src/shared/world/HouseSocketAimPolicy.luau', 'Наведение'),
    'socket-occlusion': ('src/client/world/HouseSocketAimOcclusion.luau', 'Проверка видимости'),
    'door-service': ('src/server/world/HouseDoorService.luau', 'Дверь'),
    'padlock-service': ('src/server/world/HousePadlockService.luau', 'Замок'),
    'elevator-service': ('src/server/world/HouseElevatorService.luau', 'Лифт'),
    'elevator-policy': ('src/shared/world/HouseElevatorPolicy.luau', 'Маршрутизация этажей'),
    'spawn-orientation': ('src/shared/world/HouseSpawnOrientation.luau', 'Направление spawn'),
    'camera-sync': ('src/server/character/CharacterCameraSync.luau', 'Синхронизация камеры'),
    'socket-effects': ('src/server/world/HouseSocketEffects.luau', 'Эффекты/заглушки'),
    'fireplace-service': ('src/server/world/HouseFireplaceService.luau', 'Камин и готовка'),
    'fireplace-mount': ('src/server/world/HouseSocketAssetMount.luau', 'Монтаж и Appearance'),
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

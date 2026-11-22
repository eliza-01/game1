"""House mechanics technical maps grounded in the current HouseSocketContract.

Each card can carry its own script references. The same card shape can later be
used for NPC/Monster actor-specific entries (scope='asset', assetId=slug).
No runtime logic or source code is duplicated here.
"""


def card(identifier, title, kind, summary, sockets, sections, sources):
    return {
        'id': identifier, 'title': title, 'kind': kind, 'scope': 'shared',
        'summary': summary, 'sockets': sockets, 'sections': sections,
        'sources': sources,
    }


ITEMS = [
    card('socket-registry', 'Сокеты · обнаружение и доступ', 'Контракт',
         'Только реальные Bone/Attachment у размещённого дома; сервер проверяет каждое действие.',
         ['HouseRig', 'HouseSocketContract.Definitions'], [
             {'title': 'Подключение', 'lines': [
                 'Дом определяется по Game1RealEstateSlug; в Studio разрешён авторский HouseRig с реальными известными сокетами. Шаблонные модели в Runtime не обслуживаются.',
                 'HouseSocketService один раз индексирует распознанные Bone/Attachment по точным именам HouseSocketContract. При изменении структуры выполняет адресное обновление, без покадрового обхода Workspace.',
                 'Для интерактивных сокетов сервер создаёт ProximityPrompt и принимает HouseSocketInteract. Клиент передаёт сокет и E/F, а сервер заново проверяет принадлежность дому, разрешённое действие, дистанцию и cooldown 0.45 с.',
                 'На мобильном клиенте выбранный вариант вызывается касанием; отдельной клиентской логики исполнения действий нет.',
             ]},
             {'title': 'Стабильность', 'lines': [
                 'Выгрузка или удаление модели очищает созданные prompts, эффекты и соединения.',
                 'Неизвестные имена, дубликаты и отсутствующие необходимые сокеты не подменяются вымышленными координатами. Отсутствующие имена записываются в Game1RuntimeMissingSockets.',
                 'Studio debug может менять радиусы в безопасных пределах. Эти переопределения не служат настройками игрового Runtime.',
             ]},
         ], ['socket-contract', 'socket-service', 'socket-discovery', 'socket-prompt', 'socket-aim', 'socket-occlusion', 'socket-authoring-doc']),
    card('door', 'Дверь · ручки и шарнир', 'Взаимодействие',
         'E открывает/закрывает; сторона ручки не меняет серверную механику двери.',
         ['door_01_hinge_socket', 'door_01_handle_inside_socket', 'door_01_handle_outside_socket'], [
             {'title': 'Последовательность', 'lines': [
                 'Обе ручки принадлежат DoorAssembly, привязанной к авторскому hinge; для реального поворота DoorAssembly должен иметь Game1DoorPivotMode = rigid_model.',
                 'Сервер запрещает повторный запуск во время движения, сохраняет закрытый pivot и поворачивает дверь на 90° за 0.42 с через TweenService и Model:PivotTo.',
                 'В открытом состоянии надпись меняется на «Закрыть дверь». При установленном замке открыть нельзя.',
             ]},
             {'title': 'Защита', 'lines': [
                 'Произвольный клиентский вызов не может назначить новый pivot или состояние: HouseSocketService проверяет реальный сокет, E/F и радиус (8 studs + 2 для ручек).',
                 'Движение двери, коллизии дома и socket-регистр — отдельные ответственности.',
             ]},
         ], ['socket-contract', 'socket-service', 'door-service', 'socket-authoring-doc']),
    card('padlock', 'Навесной замок', 'Взаимодействие',
         'E снять замок, F на закрытой двери навесить его при наличии ключа.',
         ['door_01_padlock_01_inside_socket', 'door_01_padlock_01_outside_socket'], [
             {'title': 'Состояние', 'lines': [
                 'При наличии хотя бы одного padlock-сокета начальное состояние Game1PadlockAttached=true. Обе стороны управляют одним состоянием дома.',
                 'При закрытой незапертой двери на ручках предлагается F «Навесить замок · ключ». Замок нельзя навесить, когда дверь открыта или движется.',
                 'Серверная проверка ключа сейчас заглушка: вне Studio она пропускает игрока, в Studio используется Game1HouseTestKeyOwned; это ещё не инвентарь MMORPG.',
                 'Визуализация замка — временный полупрозрачный Part без коллизий.',
             ]},
         ], ['socket-contract', 'socket-service', 'padlock-service', 'socket-effects']),
    card('elevator', 'Лифт · переходы между этажами', 'Взаимодействие',
         'E/F выбирают доступный этаж; координаты назначения берутся только из spawn-сокета.',
         ['elevator_01_socket', 'elevator_02_socket', 'elevator_03_socket'], [
             {'title': 'Маршруты', 'lines': [
                 'Этаж доступен только если существуют и elevator_NN_socket, и house_floor_NN_spawn_socket. Последовательность этажей 1–3 без пропусков.',
                 'В двухэтажном доме на 1-м этаже E → 2, на 2-м E → 1. При трёх этажах E ведёт выше, F — ниже, когда есть соответствующее направление.',
                 'Кнопка elevator_NN_socket не является координатой назначения. Сервер берёт CFrame целевого house_floor_NN_spawn_socket, переносит персонажа и обнуляет скорости.',
                 'После успешного перехода CharacterCameraSync отправляет направление только владельцу персонажа; наклон и zoom камеры сохраняются.',
             ]},
             {'title': 'Проверки', 'lines': [
                 'Радиус взаимодействия — 10 studs, область наведения — 5 studs, серверный cooldown — 0.45 с.',
                 'Если нет нужного этажа, кнопка действия не предлагается; клиент не может создать новое направление через RemoteEvent.',
             ]},
         ], ['socket-contract', 'socket-service', 'elevator-service', 'elevator-policy', 'spawn-orientation', 'camera-sync', 'teleport-camera-doc']),
    card('floor-spawn', 'Spawn · точка и направление этажа', 'Опора',
         'Реальный Bone задаёт положение и направление персонажа Tail → Head.',
         ['house_floor_01_spawn_socket', 'house_floor_02_spawn_socket', 'house_floor_03_spawn_socket'], [
             {'title': 'Ориентация', 'lines': [
                 'На destination spawn сервер применяет HouseSpawnOrientation.Upright: для Bone использует направление Blender Tail → Head, затем проектирует его на горизонтальную плоскость.',
                 'Камера получает тот же heading, а ControllerManager — FacingDirection. Невалидное горизонтальное направление запрещает телепорт.',
                 'Сокеты этажа не интерактивные: игрок нажимает на elevator_NN_socket, а не на spawn.',
             ]},
         ], ['socket-contract', 'spawn-orientation', 'elevator-service', 'camera-sync', 'teleport-camera-doc']),
    card('chest', 'Сундук', 'Заглушка',
         'Точка взаимодействия есть; инвентарь и открытие сундука ещё не подключены.',
         ['chest_01_socket'], [
             {'title': 'Текущее поведение', 'lines': [
                 'Сервер создаёт временную геометрию, привязанную WeldConstraint к MeshPart, и предлагает E «Открыть сундук».',
                 'После проверки расстояния (8 studs) и cooldown игрок видит «Сундук пока недоступен». Никаких предметов не выдаётся и состояния инвентаря нет.',
             ]},
         ], ['socket-contract', 'socket-service', 'socket-effects']),
    card('chimney', 'Дымоход · дым', 'Эффект',
         'Визуальный ParticleEmitter запускается на реальном socket, без действий игрока.',
         ['chimney_01_socket'], [
             {'title': 'Поведение', 'lines': [
                 'HouseSocketEffects.StartSmoke создаёт ParticleEmitter с Rate=12, Lifetime=2.7–4.3 и Speed=2–4.5.',
                 'Эффект привязан к chimney_01_socket и удаляется при unregister дома. Взаимодействие с дымом не предусмотрено.',
             ]},
         ], ['socket-contract', 'socket-service', 'socket-effects']),
    card('fireplace', 'Камин', 'Опора',
         'Опциональный socket без игрового действия; готов для будущей механики.',
         ['fireplace_01_socket'], [
             {'title': 'Текущее состояние', 'lines': [
                 'HouseSocketContract содержит необязательный fireplace_01_socket с interact=false.',
                 'Ни огонь, ни UI, ни серверное действие сейчас не создаются. Это не работающий камин.',
             ]},
         ], ['socket-contract', 'socket-service']),
    card('houseplant', 'Растения · точки декора', 'Опора',
         '15 опциональных маркеров в авторской модели, без интерактивности.',
         ['houseplant_01 … houseplant_09', 'houseplant_010 … houseplant_015'], [
             {'title': 'Контракт именования', 'lines': [
                 'Первые девять именуются houseplant_01 … houseplant_09, остальные houseplant_010 … houseplant_015, без суффикса _socket.',
                 'В HouseSocketContract эти точки не создают prompts или игровой эффект. Само их наличие не означает автоматически размещённое растение.',
             ]},
         ], ['socket-contract', 'socket-authoring-doc']),
    card('plot-pivot', 'Plot · авторские координаты дома', 'Авторинг',
         'Позиция дома привязана к участку, а не к опубликованному Model ID.',
         ['house_armature', 'plot_NN_volume'], [
             {'title': 'Позиционирование', 'lines': [
                 'Размещение хранит (plotIndex, houseLevel, houseVariant, spawnPivotLocalCFrame) относительно plot_NN_volume. Замена опубликованной модели не должна переносить дом.',
                 'Общий pivot берётся из авторского house_armature, совместного с MeshPart. land_spawn_01_socket не является Pivot участка.',
                 'Сокеты должны существовать в FBX, Lua не создаёт отсутствующие Bones. Коллизии авторятся отдельным Collision Blueprint, независимо от сокетов.',
             ]},
         ], ['socket-authoring-doc', 'socket-ownership-doc']),
]

"""Technical card for windmill_02: distinct visual and server roles."""
ITEMS = [
    {
        'id': 'windmill-02', 'title': 'Windmill 02 · вращение и дверь',
        'kind': 'Location mechanic', 'scope': 'asset', 'assetId': 'windmill_02',
        'summary': 'Лопасти и fabric: один общий pivot, 360° за 3 сек. Дверь: F на handle socket, hinge bone.',
        'sockets': ['windmill_door_socket', 'windmill_door_handle_socket', 'blades', 'fabric'],
        'sections': [
            {'title': 'Rotations', 'lines': [
                'Options → Rotations → Windmill 02 задаёт enabled и secondsPerRevolution (по умолчанию 3).',
                'Client визуально поворачивает blades + fabric на одинаковый угол вокруг центра fabric; физика неподвижна.',
                'Не требуется windmill_rotation_socket: жёсткий ротор не зависит от FBX Skin.',
            ]},
            {'title': 'Door', 'lines': [
                'windmill_door_socket — авторский деформирующий hinge Bone для door.',
                'windmill_door_handle_socket — обязательный отдельный Attachment/Bone для F prompt и проверки расстояния.',
                'Сервер меняет состояние двери, клиент анимирует Bone.Transform; скиннинг двери сохраняется.',
                'Если нет одного из сокетов или они неоднозначны, взаимодействие не создаётся.',
            ]},
        ],
        'sources': ['windmill-rotation-client','windmill-door-client','windmill-observer-client',
                    'windmill-door-server','windmill-options','windmill-doc'],
    },
]

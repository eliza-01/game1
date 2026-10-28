# M148 · House socket discovery в любом месте Workspace

База: **M147**, без изменения SQLite, опубликованных ассетов, FBX и Studio Bridge.

## Наблюдение из реального дерева (28.10.2026)

В Workspace найдены `house_level4_01` и `house_level4_3` с `Game1RealEstateSlug=house_level4_01`.
Обе модели содержат `HouseRig/house` с шестью Bone (chest/chimney/elevator/три spawn)
и `DoorAssembly/DoorRig/door` с четырьмя Bone (hinge/inside/outside/padlock).
Контракт определяет девять рабочих точек; hinge — только опорная точка двери.
В снимке было 0 `ProximityPrompt`; снимок дерева сам по себе не доказывает,
выполнился ли `HouseSocketService.Start()` именно в Play.

## Исправления

- Доменное распознавание вынесено в `HouseSocketDiscovery`.
- На опубликованном runtime дом определяется по `Game1RealEstateSlug` где угодно под Workspace.
- Только в Studio допускается предварительный house без slug, когда в прямом `HouseRig`
  реально существует Bone/Attachment из контракта. Имя модели и папка не используются.
- Клиентское отображение радиусов поддерживает тот же Studio-only preview до появления slug.
- Учитываются поздняя установка `Game1RealEstateSlug`, добавление/удаление сокетов
  и вставка `HouseRig` в уже размещённую модель.
- Кандидаты сканируются однократно при запуске и при адресных событиях; ни одного
  полного поиска Workspace на Heartbeat. Для каждого дома — один проход по descendants.
- Сбой обработки одного дома не прерывает регистрацию остальных.

## Проверка после запуска Play

Нужна строка `[game1][house-socket] ready · ...` с ненулевым `prompt(s)`.
Обнаружение дома, 3D-подсказки и их server-side триггеры проверяются именно в Play,
не через Command Bar в Edit Mode. Реальный Roblox Play здесь не запускался.
Если строка отсутствует, необходимо проверить синхронизацию Rojo и предупреждения
`[game1][bootstrap] HouseSocketService ...` в Output — само дерево не заменяет эту проверку.

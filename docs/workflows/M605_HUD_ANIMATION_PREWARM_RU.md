# M605 — объединение M604 и прогрева

База M603. M604 отдельно не устанавливается.

- HUD: общий правый device-safe край 2 px для Attack/Skill4/weapon grid. Jump под Skill1; общий размер 46% Attack, weapon 37%. Дуга 1.28 диаметра для раздельных прямоугольных hit targets. CoreUI safe rect только для масштаба. Проверить на телефоне с вырезом, при повороте и в Studio emulator.
- Lock над Door при совместном показе. Остальные E/F actions прежние. Wallet / touch controls / debug launchers / context actions используют HudButtonTheme. SVG/PNG Attack, Jump, Aim и house используют один клиентский кэш `HudSvgIcons`; EditableImage требует разрешений Experience. При запрете — резервный символ; опубликованные PNG IDs можно прописать в `published`.
- WorldAnimationPreloader один раз за клиентскую сессию собирает уникальные опубликованные animationId из MonsterAnimationRegistry и NpcAnimationRegistry (сейчас 23). Typed Animation instances в батчах до 16, без создания удалённых Animator. CharacterAnimationController сохраняет свой cache prewarm, world entry ожидает результаты обоих jobs максимум ещё 12 секунд после mesh preloading. Смена модели отменяет ожидание. При ошибках/таймауте — warning и on-demand загрузка. Без Character Creation прогрев фоновый.
- Death: сервер начинает Death перед fade исходящих треков; PreSimulation compositor NPC/Monster освобождает sampler без записи бегущих ног при LifeState != Alive. Terminal hold, corpse sink, respawn и damage не изменены. Это устраняет выявленное пересечение владельцев позы, но не подтверждает причину каждого rest pose кадра.

## Приёмка Studio / опубликованный DEV

1. Холодный вход на PC и Mobile. До снятия curtain дождаться `[game1][animation] prewarm ...` и `[game1][world-animation] prewarm ...`. При таймауте проверить предупреждения и последующий playback.
2. Убить впервые и повторно монстра/NPC в idle, run и moving attack; записать момент вспышки (первый кадр Death или переход DeathIdle). Проверить terminal pose, sink, respawn, низкий FPS, другой клиент.
3. Проверить создание/выбор нового персонажа, повторный вход и respawn, отсутствие повторной загрузки каталога мира. Смена персонажа не использует старый cache.
4. Проверить три SVG на мобильном и состояния Aim, порядок замка/двери и alignment weapon/skill4/attack; разрешение EditableImage или опубликованные PNG IDs.

# M481 · Character Creation — authored pivots and responsive interface

## Источники

Пять камер из M479 остаются неизменными. Две позиции и повороты сняты с
Properties в Studio (оба исходных Test Stand в скриншотах подписаны
`human_female_01`, поэтому первая позиция назначена Male, вторая Female):

| Preview | World pivot XYZ | Rotation XYZ (degrees) |
|---|---|---|
| human_male | 179.449, -314.025, 176.096 | 0, -35.501, 0 |
| human_female | 177.640, -314.025, 167.780 | 0, -93.433, 0 |

Их источник для runtime — OptionsStore → `characterCreation.spawnPoints` →
`GameOptionsRegistry`, а не хардкод в клиентском контроллере.

## Миграция

`m481_creation_scene_points.py` заменяет **только** старые дефолтные M480
плейсхолдеры (или нулевые плейсхолдеры). Авторские координаты сохраняются.
Плейсхолдеры переводятся на заданные точки, старый флаг поиска отсутствующих
Studio-маркеров отключается. Размер панели M480 `340/290` меняется на
`460/330`, явные иные пользовательские размеры сохраняются. Создаётся backup
`options.json.pre-m481-*.bak`. Существующие Camera CFrame/FOV не изменяются.
Повторное применение миграции безопасно. Registry создаётся штатным
`OptionsStore`, чтобы не было несовпадения JSON/Luau.

## Client UI

`CharacterCreationPanel` — только композиция/адаптивные размеры,
`CharacterCreationAppearanceView` — один активный раздел опубликованной
внешности. `CharacterCreationController` — состояние, переводы, камеры, вызовы
серверных RemoteFunction. `CharacterCreationPreviewController` — только
локальные собранные Models. `CharacterCreationStageVisibility` временно
скрывает отмеченные `Game1CharacterTestStand` модели только у этого игрока,
восстанавливая их свойства после закрытия. Нет отдельного Camera Controller.

Верх (title, gender), навигация (hair/eyebrows/eyes/head) и низ
(face/full, overview, enter world) постоянно доступны. Только содержимое
активной вкладки при необходимости прокручивается. Мобильные вкладки
показываются в два ряда, чтобы подписи не обрезались.

Два клиента на одном сервере получают независимые локальные превью.
Server-side template cache только для опубликованных и валидированных рецептов.
Запросы первого Male/Female превью выполняются последовательно, учитывая
`CharacterCreationPreviewService` per-player busy guard.

## Проверка в Studio Play

1. Убедиться, что включён Options → Character Creation и выполнен Rojo Sync.
2. Обе модели стоят раздельно в заданных точках, смотрят на захваченные камеры,
   не зависают в нуле Place. В Output — две строки `preview positioned`.
3. На обзорной камере оба персонажа видны; Male/Female → полный рост; вкладка
   лица → правильная Face camera, без конфликта с gameplay-camera.
4. Hair, eyes, eyebrows, head и цветовые палитры доступны на desktop/mobile;
   туловище и броня недоступны; действия внизу всегда видны.
5. Закрытие режима восстанавливает авторские Test Stand на локальном клиенте.
6. `Enter World` собирает только выбранный сервером проверенный рецепт.

Описанные Play проверки должны быть проведены в Roblox Studio отдельно;
статические тесты не удостоверяют положение MeshPart и итоговую композицию.

# M479 · Character Creation · авторская сцена и первый экран

Текущая стадия: первый работающий проход выбора Human Male / Female, без сохранения внешности.

## Камеры

Источник Studio: `Workspace.Places.Character Creation.Game1CharacterCreationCameras`.

1. `SelectionOverview` — общий план Male/Female.
2. `MaleFullBody` — Male, полный рост.
3. `FemaleFullBody` — Female, полный рост.
4. `MaleFace` — лицо Male.
5. `FemaleFace` — лицо Female.

Camera Anchors уже сняты в Studio Edit 25 ноября. Координаты Output записаны в `options.json` как переносимый fallback. При включённом `useStudioAnchors` клиент использует настоящие анкоры, если они реплицированы. Переходы выполняет тот же `CameraController`, который ведёт обычную игру.

## Контракты

- Options → Character Creation управляет включением, 5 CFrame/FOV, временем переходов и размером панели.
- `GameOptionsRegistry` — единственный runtime-источник настроек.
- `CharacterCreationGateway` разрешает только `human_male` / `human_female` с `ASSEMBLY_READY`; не принимает от клиента Asset ID или recipe.
- `CharacterService` собирает выбранный персонаж существующим `CharacterAssemblyBuilder` / `CharacterRigService`.
- Клиентская UI-сцена не создаёт отдельный персонаж в Workspace и не копирует логику ригов.
- Включение по умолчанию **false** до проверки Studio Play / StreamingEnabled / опубликованного Runtime.
- Если один из базовых персонажей не готов, сервер переходит к прежнему спавну.

## Оставшаяся реализация до полноценной MMO-системы

- Не сохраняются слоты/имена/внешность; текущий экран выбирает стартовый пол/assembly только в текущей сессии.
- Переключение причёсок, пары бровей, анимации Idle/Social на сценических моделях — следующим отдельным контрактом, использующим авторские части и существующий Social Animation Playback.
- Для визуализации двух персонажей в самой сцене требуются авторские презентационные модели. Пять камер сами по себе не создают манекенов.
- Перед включением в опубликованной игре проверить наличие/стриминг сцены, переход в мир и локализацию мобильного UI.

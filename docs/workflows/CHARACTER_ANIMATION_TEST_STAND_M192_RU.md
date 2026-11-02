# M192 — Character Animation Test Stand (Studio authoring / Play)

## Цель и границы

В модульной системе Characters нет необходимости сохранять собранную модель как
основной ServerStorage template: игровой `CharacterService` уже вызывает
`CharacterAssemblyBuilder.Build()` с опубликованными component Model Assets.
Для визуальной проверки размеров, костей, одежды и анимаций реализован
**изолированный Studio-only стенд**, а не второй путь публикации/сборки.

### Авторы состояния

| Область | Owner | Обязанности |
|---|---|---|
| Рецепты | `CharacterRegistry` | Чтение доступных archetype и `assembly` |
| Сборка | `CharacterAssemblyBuilder` | Тот же `rig_carrier`, bones, mounts, atlas, что и runtime |
| Studio adapter | `StudioCharacterStandBuilder` | `AssetService:LoadAssetAsync` → загрузка опубликованных моделей → runtime Builder |
| UI/оркестрация | `StudioCharacterTestStand`, `StudioCharacterStandWidget` | Выбор профиля, один черновик, размещение, UX/очистка |
| Размещение | `StudioCharacterStandPlacement` | Только Workspace clone, поверхность, prompt, имя, anchor |
| Источник анимаций | `CharacterAnimationRegistry` + `CharacterStandAnimationCatalog` | Сортировка опубликованных Animation Asset ID; procedural-only исключены |
| Studio Play | `CharacterTestStand.server.luau`, `CharacterTestStandPlayback` | Подписки на prompt, один Animator/track на модель, cleanup |

## Использование

1. Применить M192. Привести Rojo к текущему состоянию, выполнить `& .\system\studio-plugin\install.ps1`; полностью закрыть Studio и открыть заново.
2. В Studio Edit нажать кнопку `Character Stand` на панели `game1`.
3. В Dock выбрать профиль (кнопка профиля переключает зарегистрированные archetypes), затем **Собрать персонажа**. Для `visualMode=assembly` нужна `assembly.ready=true`; для `model` — опубликованный Model Asset ID.
4. Дождаться сообщения об успешной сборке. Нажать **Поставить на поверхность**, кликнуть по доступному Part/Terrain. Нужна горизонтальная поверхность. Персонаж появляется в `Workspace.Game1CharacterTestStands`. Кнопку можно использовать снова для дополнительных копий.
5. Нажать **Play**. Рядом с тестовой моделью появляется системный Roblox ProximityPrompt **E — Следующая анимация**. Каждое нажатие перебирает все опубликованные `base`, `emotions` и `weapons` выбранного профиля в устойчивом порядке. Текущий clip, индекс и тип действия выводятся в Output и записываются в атрибуты модели.
6. Остановить Play. Модели сохранятся в Edit Workspace; при необходимости их можно удалить в Explorer или через Undo.

## Безопасность и ограничения

- Скрипт воспроизведения **немедленно завершается вне Studio** через `RunService:IsStudio()`; он не подключает RemoteEvents, не трогает игроков, combat/state, не создаёт регистров и не публикует ассеты.
- Авторский плагин работает только в Edit; модель-черновик не записывается в ServerStorage/Workspace до клика по поверхности. После разгрузки плагина черновик удаляется.
- Все BasePart стенда anchored, CanCollide/CanTouch/CanQuery отключены. Они не должны влиять на игровую физику и не являются полноценными игроками/манекенами для hitbox тестирования.
- Процедурные документы эмоций без опубликованного Animation Asset ID исключены: отдельный движок facial events намеренно не дублируется. Для таких профилей может не быть E-переключения.
- При несоответствии skeleton signature анимации блокируются с предупреждением; никакого неявного retarget.
- Требуются доступные Studio опубликованные Model/Animation Assets с нужными правами, текущие Rojo `CharacterRegistry`, `CharacterAnimationRegistry` и `CharacterAssemblyBuilder`.
- В Studio нужно проверить фактическую работу `Animator:LoadAnimation`, нажатие E, bounds/ground placement и Roblox Skinning. Python source-only тесты не способны подтвердить это.

## Не менялось

`CharacterService`, `CharacterAssemblyBuilder`, `CharacterAtlasBinder`, `CharacterRegistry`, `CharacterAnimationRegistry`, схемы SQLite, опубликованные ID и пайплайны import/FBX/queue. Внедрение самостоятельного тестового стенда НЕ заменяет `Test Loadout` и не вмешивается в основную регистрационную систему.

## Откат

Вернуть исходные файлы патчем `git apply -R`, удалить оставшиеся модели только из `Workspace.Game1CharacterTestStands` по необходимости, снова установить Studio-плагин. Изменений persistent data/Asset ID нет.

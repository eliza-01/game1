# Characters: персонаж-сборка v1

> UI-уточнение без изменения backend: [M173 — Modular Characters](CHARACTERS_MODULAR_UI_M173_RU.md).

## Запись персонажа и общие части

`human` — профиль скелета. `human_male` — отдельная запись персонажа со стартовыми
характеристиками и рецептом внешности. Меши повторно не регистрируются и не
публикуются при сохранении рецепта. Пол определяется выбранной головой; тело
и броня остаются общими. Собственный скелет причёски допустим внутри аксессуара.

В Characters новый блок **Character assemblies** содержит:

- ID и display name; зарегистрированный rig.
- Starter set: заполняет `upper/lower/gloves/boots`. Любой слот можно заменить
  частью другого совместимого сета. Смена сета снова заполняет эти четыре слота.
- `head`, `eyes`, `eyebrows`, `hair`; в hair доступны пол головы и common.
- Starting stats. Изменения и рецепт сохраняются одной операцией с ревизией.
- Таблицу готовности и **Set as Startup**. Выбор строки в левом дереве открывает
  редактор рецепта; цельные модели редактируются прежним интерфейсом.

Все восемь слотов обязательны для стартового рецепта. Служебная спираль глаз
`role=effect` не участвует в выборе обычных глаз. Обработку эффектов и анимации
этот этап не вводит. Стартовый вид не означает выдачу всех частей каталога в
инвентарь: сохраняется только серверный рецепт внешности.

## Готовность и публикации

Рецепт можно сохранить до публикации. Назначение startup запрещено, пока у рига,
всех выбранных частей и явно подключённых атласов нет опубликованных ID.
Backend проверяет это повторно; отключённая кнопка не является единственной
защитой. Сохранение рецепта не меняет startup и не выполняет upload.

Подготовка замены компонента сохраняет последний опубликованный ID и его bind
metadata. Runtime-рецепт использует именно опубликованную ревизию, а не metadata
неопубликованного FBX. При успешной публикации части/смене atlas binding registry
перегенерируется. Если историческая bind metadata отсутствует, готовность
блокируется, скрытая подмена новой metadata запрещена.

Один rig может обслуживать мужской и женский рецепты с общей бронёй. Старый
`human_female` типа `model` не заменяется рецептом с тем же ID автоматически.
Пути identity/whole-model replacement отклоняют попытку редактировать assembly
как цельный FBX. Переименование рецептов и перевод legacy ID — отдельная миграция.

## Хранение и совместимость

К `characters` добавлены `visual_mode` (по умолчанию model) и `assembly_json`.
Миграция идемпотентна, перед ALTER создаётся SQLite online backup
`.control-center/backups/before_character_assemblies_<id>.db`.
`character_assembly_history` сохраняет прошлые рецепты и стартовые stats.
Запись обновляется с `expected_revision`; устаревший редактор не перетирает новую.

Старые записи/Asset IDs/анимационные таблицы сохраняются. Существующий
`character-archetypes.json`/`CharacterRegistry.luau` schema 5 получает аддитивные
поля `visualMode` и `assembly`; вложенный контракт имеет `schema_version=1`.
`model.assetId` у сборки пустой, единого опубликованного mesh bundle не требуется.
Существующее `active_character_archetype_id` используется для обоих типов.

HTTP:

- `GET /api/characters/assemblies`: рецепты, совместимый каталог и stats options.
- `POST /api/characters/assemblies`: `{id, display_name, rig_id, set_id,
  parts:{upper,lower,gloves,boots,head,eyes,eyebrows,hair}, stats, expected_revision}`.
  Без явных body overrides значения выводятся из set_id.
- `POST /api/characters/<id>/activate`: общий маршрут; для assembly обязательна
  актуальная серверная проверка зависимостей.

## Runtime

CharacterService различает `model` и `assembly`. Цельная модель сохраняет прежний
путь ServerStorage/InsertService. Для сборки используется CharacterAssemblyBuilder
с серверным loader/cache и fingerprint опубликованных зависимостей.

- Постоянный `rig_carrier` содержит канонические Bone, невидим и неколлизионен.
- Семь основных skinned MeshParts выравниваются по bind-положениям общих костей,
  проверяются и подключаются Weld к carrier внутри одного ImportedRig Model.
  Дубли Bone в этих частях удаляются; их skin data остаётся в mesh asset.
- Волосы сохраняют собственные Bone и соединяются RigidConstraint через
  `hair_bone_socket` с канонической `hair_mount`.
- Создаются RootPart и один AnimationController/Animator; далее используется
  существующий CharacterRigService, без изменения gameplay collision/controller.
- При ошибке сборки незавершённая модель уничтожается, текущий персонаж сохраняется.
  Явно выбранный персонаж никогда не подменяется bootstrap-моделью. Причина доступна
  в предупреждении сервера и атрибуте Player.CharacterLoadError. Bootstrap допустим
  только при отсутствии выбора персонажа.
- Проверяются bind-положения всех фактически импортированных Bone. Исходный
  used_bones может содержать исчезнувшие после квантования весов влияния: они не
  обязаны иметь Bone в отдельной части. Полный набор костей канонического carrier
  обязателен; неизвестные кости и несовместимые bind-положения отклоняются.
- Atlas ColorMap нельзя задавать обычным runtime setter: используется
  AssetService.CreateSurfaceAppearanceAsync, затем clone готового appearance.
  Документация: https://create.roblox.com/docs/reference/engine/classes/SurfaceAppearance
  и https://create.roblox.com/docs/reference/engine/classes/AssetService.

Этот этап не меняет клипы, animation scope и правила управления состояниями лица.
Новая запись без анимационного профиля сама по себе не получает анимации.

## Применённое состояние и проверка

Сохранён `human_male`: rig human, set newborn, head_01_male, eyes_01,
eyebrows_01, hair_02_common. Все части зарегистрированы, но ещё не опубликованы.
На момент этого старого отчёта запись была ASSEMBLY_DRAFT, startup был human_female. **Это исторический снимок:** в дампе 2026-10-31 `human_male` уже ASSEMBLY_READY и является startup; актуальное состояние определяет `activeArchetypeId`.

Проверены настоящая миграция на копии рабочей DB и сохранность legacy ID/startup;
смешивание сетов, пол волос, исключение effects, optimistic edits, finite stats,
публикационная готовность и bind metadata прошлой опубликованной ревизии.

Studio Play: синтетические MeshParts/Bone через настоящий builder и текущий
CharacterRigService; один Animator, main skeleton, аксессуарное крепление,
отклонение несовместимого bind/unready recipe, клонирование без изменения cache.
Существующий human_female появился с Visual. Studio возвращён в Edit.

Первоначальная проверка выше была синтетической. После публикации пользователем
обнаружен реальный сбой: импорт eyes_01 не содержит face_eye_seg05_l/r, хотя они
перечислены в исходном used_bones. EditableMesh опубликованного ассета подтвердил
отсутствие этих влияний. Исправленная проверка импортированного скелета собирает
все восемь опубликованных частей без изменения ID и перепубликации.
Readiness в каталоге означает наличие опубликованных зависимостей; это не заменяет
Studio Play-проверку реального импорта. Atlas rendering и анимации проверяются отдельно.

Откат: предыдущий рецепт/stats из character_assembly_history. Откат кода — обратный
патч; для legacy запуска можно оставить активным human_female. Полный DB backup
не восстанавливать поверх более новых несвязанных изменений.

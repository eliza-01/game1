# M277 — чистый Character Catalog v2 и стартовый персонаж

## Источники истины

- `CharacterComponents` — зарегистрированные/опубликованные rig и MeshPart. Только канонические имена `human_(male|female|common)_mNNN_<slot>`; rig — `human_female`, `human_male` или общий `human`, если реально опубликован и совместим.
- `ArmorCatalog` — игровой комплект, необязательные armor slots, gender-specific/unisex варианты с MeshPart + Appearance (Atlas Registry). Имя `newborn_*` больше не используется как название набора.
- `CharacterAssemblies` — v2-рецепт: rig, явный `gender`, один Armor Set и независимые `head/eye_l/eye_r/eyebrow_l/eyebrow_r/hair`. Пустые лицевые слоты допустимы, `head` обязателен. Статы и hair-color channels хранятся с рецептом.
- `default_character_assembly_id` — базовая готовая сборка для игрового создания персонажа и текущего production startup; не выдаёт игровых прав.
- `studio_admin_assembly_id` — изолированная тестовая сборка **только в Roblox Studio Play**. Set as admin означает выбор модели для симуляции, не назначение администратора/прав доступа.

Для обоих selectors требуется опубликованный rig и готовый resolver (`ready: true`). Черновики сохраняются, но не активируются. Если в игре отсутствует валидный default или в Studio отсутствуют и admin, и default, сервер пишет понятную ошибку `CharacterLoadError` вместо молчаливой подстановки старого Bootstrap.

## Ручная очистка M277

Миграцию **не** выполнять автоматически при старте. Сначала применить код, остановить Host Agent, затем выполнить `migrate_character_catalog_m277.py` в preview и apply. Для Character atlas сначала отдельно выполнить M276 (если ещё не выполнена); атласы и Roblox Image IDs M277 не изменяет.

На проверенной БД 2026-11-10 удаляются **из активного** каталога 11 старых part (`newborn_*`, `head_01_male`, `eyes_01*`, `eyebrows_01`, `hair_0x_common`), старый rig `human`, устаревший `newborn` component set и два old-character archetype (`human_female` whole-model, `human_male` v1). Новые `human_female_*`, `human_common_*` и rig `human_female` остаются. Так освобождается ID `human_female` для создания нового v2-рецепта.

Старые профили анимаций также исключаются из активного каталога: в проверенной БД это **2 профиля, 36 clips, 36 bindings и 13 clip documents**. Их полные записи перемещаются в `character_retired_animation_records_m277`; 27 исторических `animation_publications` остаются. Новые `human_female` animations не могут автоматически использовать 162-bone анимации прежней модели — требуется осознанная новая регистрация/проверка на 77-bone rig.

Перед изменением БД создаётся полная копия в `.control-center/backups/before_character_catalog_m277_*.db`. История публикаций, исходники FBX и анимаций, опубликованные Roblox Model/Image/Animation IDs **не удаляются**. Старые записи больше не появляются в активном списке компонентов; восстановление возможно через SQLite backup.

Операция идемпотентна. Непредусмотренные старые имена, ссылки Armor v2 на удаляемые меши и случаи конфликта со студийным selector блокируют миграцию без частичных изменений.

## Workflow

1. Удалить активное legacy через M277; обновить Asset Manager.
2. Открыть **Базовая сборка персонажа**, нажать **New character**. По умолчанию предлагается `human_female` с `human_female` rig и Female (можно поменять).
3. Выбрать опубликованный Armor Set (`peasant_clothes`). У каждого **зарегистрированного слота** комплекта назначить v2 MeshPart + уже опубликованный Appearance в Armor Catalog. Отсутствующие слоты комплекта допустимы.
4. В редакторе выбрать `head` и остальные желаемые `eye_l`, `eye_r`, `eyebrow_l`, `eyebrow_r`, `hair` отдельно. Для solid colors Atlas не обязателен.
5. **Save recipe & starting stats**. Пока не назначены ресурсы, статус `DRAFT` и кнопки профилей недоступны. После публикации всех зависимостей — `READY`.
6. Нажать **Set as default**, чтобы эта базовая сборка была startup по умолчанию (и могла использоваться будущим экраном кастомизации), и **Set as admin**, чтобы тот же либо другой рецепт использовался при Studio Play.
7. Перезапустить Studio Play после обновления Rojo-модуля `CharacterRegistry` (производится при запуске Host Agent). При ошибке смотреть `Player.CharacterLoadError` и предупреждения `[game1]` в Output.

Удалённый whole-model Character authoring API возвращает HTTP 410; нельзя скрытно восстановить устаревшие записи через прежнюю кнопку Reg+Publish. Экран полноценной **игровой** кастомизации не входит в M277: default-выбор и resolver готовы, а игровые UI/сохранение созданного игроком аватара — отдельная задача.

## Область проверки

Проверки M277: очистка на копии реальной БД, повторная миграция, публикационная история, сохранение черновика, блокировка admin на DRAFT, готовая female сборка с одной armor part, независимый default/admin, Luau preflight, общий verify после очистки. Play в Roblox Studio необходимо подтвердить вручную; это не имитируется статическим тестом.

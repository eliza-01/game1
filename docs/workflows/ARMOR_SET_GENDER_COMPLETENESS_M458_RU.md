# M458 · Контроль комплектности Armor Sets по полу и по ригу

## Владельцы данных

- `character_core/armor.py` продолжает владеть SQLite-каталогом комплектов и существующим `ArmorCatalog.resolve` для конкретной пары `(gender, rigId)`.
- `character_core/armor_readiness.py` — чистая, read-only проверка полноты назначений для `male` и `female` на выбранных слотах, без публикации, сохранения или редактирования ригов.
- `static/armor-readiness.js` — представление двух проверок в Character → Armor, не вычисляет контракт пригодности самостоятельно.

## Контракт

- Сет — один логический ID с необязательными слотами. Для **каждого добавленного слота** требуется работоспособный Male- и Female-вариант. Пол может получать свой вариант или `unisex` fallback; явный неполный Male/Female override **не** заменяется unisex.
- `common` / `allowedGenders` — только разрешение использовать MeshPart. Реальная cross-rig совместимость определяется только `CharacterComponents.part_compatible_with_rig` с опубликованной bind pose; сохранять общие перчатки/ботинки для нового рига автоматически нельзя.
- Snapshot `/api/armor` остаётся `schema_version=2`: добавлены только необязательные для старых потребителей поля `sets[].readiness` и `sets[].rigReadiness`. SQL-схема и ID не меняются.
- Несохранённые/неопубликованные варианты считаются черновиками. Их можно сохранять, но готовыми они не объявляются; `ArmorCatalog.resolve` не позволяет экипировать недостающий или несовместимый слот.
- Существующие зарегистрированные сеты не изменяются. Никаких новых публикаций или миграций нет.

## Регрессии

- `python -m unittest discover -s system/verify -p test_m458_armor_gender_pair_readiness.py -q`
- `python -m unittest discover -s system/verify -p test_character_armor_v2_m269.py -q`
- `node system/verify/armor_readiness_m458.js`
- `node --check system/control-center/static/character-armor.js`
- `python system/verify/verify.py`

После установки проверить в Control Center, что `Peasant Clothes` отражает нехватку Male Upper/Lower, а `human_male` отдельно показывает несовместимые с ним Common Gloves/Boots. Выбор Male/Female в строке слота должен открывать соответствующий редактор, без изменения публикации и материалов.

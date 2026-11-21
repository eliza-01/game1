# M400 · Location Assets — единое назначение Appearance

- `Location Assets → Edit → Model · FBX`: default Material/Color, Alpha, выбор/публикация Atlas через **существующий** `game1ConsumerAtlasEditor`, и отдельные `MeshPart` overrides. `Texture · atlas` в этом редакторе удалён. Центральный `Atlas Registry` остаётся.
- В новых формах только `material` и `material_atlas`. В истории могут оставаться `atlas`-записи — редактор показывает их как `material_atlas`, при последующем явном сохранении записывает новое значение и **не меняет Image ID**.
- Начальный визуальный материал новой регистрации — `Plastic`; `SmoothPlastic` доступен в палитре. Существующие значения `SmoothPlastic` не перезаписываются.
- Для MeshPart список атласов группируется общим `game1ConsumerAtlasEditor.sections` по реальным потребителям: Location, Real Estate, Character, Weapon, NPC, Shared. `0` наследует default, если он использует атлас; иначе требуется выбрать вариант явно.
- `rig_carrier` не является визуальным MeshPart и не получает Appearance. Все данные скелета, свет, огонь, коллизии и опубликованные модели сохраняются.
- Выбор/публикация Atlas, сохранение `Material/Color/Alpha` и фактический Studio Sync — **разные действия**. Никакого автоматического Studio Sync при редактировании.
- Чтение legacy `atlas` в общих Python/Studio контрактах сохранено для обратной совместимости, без новых авторских UI-опций. Real Estate также отображает только два режима, но его отдельная публикация FBX/атласов и Studio Sync не изменены.

Проверки: `node system/verify/location_appearance_ui_m400.js`, `python -m unittest discover -s system/verify -p test_m400_unified_appearance.py -q`, существующие M382/M384/AtlasRegistry/Real Estate, Luau и `verify.py`. Реальный Sync требует проверки в Studio после установки.

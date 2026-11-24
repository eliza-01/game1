# M469 · Ручное назначение Common Animations

Область: Characters → Animations → Common. Патч над M468.

- Список включает опубликованные и Approved анимации из активного семейства (`race`), в том числе из Male и Female. Черновики, изменённые или не одобренные публикации не предлагаются.
- Строка показывает контекст (`base`, `social`, `emotions`, `weapon`), слот, вариант, источник (пол/персонаж), Roblox Animation ID и совместимость рига. Поиск не изменяет данные.
- Несовместимые варианты видны с причиной, но назначить их нельзя. UI использует тот же серверный валидатор, что и POST `/api/animations/shared`; сервер повторно проверяет состояние при записи.
- Назначение создаёт или заменяет ссылку по ключу `(family, scope, weapon_set, slot, variant)`, не копирует клип, Animation ID или файлы. Удаление Common не удаляет исходную анимацию.
- Если у персонажа есть собственный опубликованный клип в слоте, он имеет приоритет над Common по правилам M468. Изменение Common пересобирает Runtime Registry; для Studio Play нужен Rojo Sync / перезапуск Play.
- Backend: `animation_core/shared.py` (подбор кандидатов, общий валидатор), `animation_core/storage.py` (snapshot). Frontend: `character-animation-ui.js`, `index.html`, `character-animations.css`. Новых HTTP-маршрутов и таблиц SQLite нет.

Проверки: `test_m468_shared_character_animations.py`, `test_m469_common_animation_picker.py`, `node --check`, `validate_luau.py`, `verify.py`. Физический Studio Play проверяется отдельно.

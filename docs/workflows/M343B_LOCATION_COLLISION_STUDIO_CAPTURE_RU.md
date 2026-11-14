# M343B — Location Assets: Collision Blueprint Studio Capture / Preview

**База:** M343A1. **Область:** только Location Assets; Real Estate и World Streaming не меняются. **В Studio ещё не проверено** (проверки кода и локального HTTP transport пройдены).

## Что появилось

- В Control Center → **Location Assets** → под библиотекой расположена отдельная панель **Collision Blueprint**. Каждая строка в библиотеке имеет кнопку **Collision** для выбора данного slug.
- `Validate` считывает выбранные Parts в Studio, проверяет Roblox Parts и показывает diff без записи в SQLite.
- `Capture` выполняет ту же проверку и сохраняет следующую ревизию в таблицу M343A; если данные совпадают, ревизия не увеличивается.
- `Preview saved` показывает сохранённые рецепты поверх выбранной Model зелёными контурами в отдельной временной папке `Workspace.__Game1LocationCollisionPreview`. Прозрачные preview-Parts имеют `CanCollide = false`, `CanTouch = false`, `CanQuery = false`, `Anchored = true`.
- `Clear Preview` удаляет **только** помеченную плагином временную папку. При выгрузке плагина preview также удаляется. Если имя занято чужим объектом — операция отказывается его удалять.
- `Revision history` показывает номера, количество Parts, краткий sha256 и время сохранения.
- Студийная команда `location-collision-authoring-v1` и результат `/location-collision-result` используют operation ID, контроль slug/phase/revision, одноразовый localhost HTTP transport с токеном Bridge. Другие команды Studio Bridge не меняются.

## Как сделать первый Blueprint — M343B1 (без папок и ручного Pivot)

1. После установки Game1Bridge открой Studio в **Edit Mode** и выбери в Asset Manager соответствующий зарегистрированный Location Asset.
2. В `Workspace` **выдели Model уже размещённого экземпляра** этого ассета (в том числе внутри `Workspace.Places` или `Workspace.Plots`). Имя модели не обязано совпадать со slug. Выделение проверяется по **полной сигнатуре опубликованных визуальных Mesh ID**, а не только по имени или атрибуту. При отсутствии инвентаризации опубликованных Mesh ID сначала обнови Place Registry / историю публикации.
3. Дополнительно выдели **любое количество 1–256** `Part`, `WedgePart`, `CornerWedgePart`. Они могут находиться в любом месте Workspace и в любых вложенных каталогах. Нельзя выбирать другой `Model`, `MeshPart` или объекты вне Workspace. Никакой `CollisionAuthoring`, атрибутов, специальных имён или изменения `CanCollide` не требуется.
4. Нажми **Validate**, проверь разницу с сохранённой ревизией, затем **Capture**. Ничего не двигаем, не переименовываем и не удаляем. Для одинаковых или русскоязычных имён Parts ID генерируется автоматически.
5. **Preview saved** — достаточно выделить одну соответствующую Model; контуры покажутся относительно её **существующего** `GetPivot()`; **Clear Preview** удалит лишь временный просмотр.

Сохраняем локальные координаты: `localCFrame = selectedModel:GetPivot():ToObjectSpace(selectedPart.CFrame)`. Источник Blender и Pivot не меняются. Blueprint применяется ко **всем экземплярам одного типа** (автоматический Collision Sync будет реализован в M343C). Выделенные исходные Parts остаются в Workspace в неизменном виде — при необходимости удаляй свои временные авторские Parts сам.

Ограничения версии: Model с `GetScale() != 1` требует отдельной поддержки масштабирования в Collision Sync, поэтому Validate его отклоняет вместо сохранения неверного Blueprint. Две разные зарегистрированные модели с полностью одинаковыми опубликованными Mesh ID тоже не могут быть безопасно различены и будут отклонены. Важная проверка Studio после установки обязательна.

## Что сознательно НЕ реализовано

- Никаких физических коллайдеров на размещённых объектах в Place, никакого `Place/Sync/Clear` новых коллизий — это M343C.
- Никаких изменений публикации Atlas/Material+Color/TextureID — это M343D.
- Preview — только авторский визуальный просмотр в Studio; при постоянной работе его нужно очищать.

## Проверки перед фактической приёмкой

```powershell
python -m unittest discover -s system\verify -p "test_location_collision_studio_m343b.py" -v
python -m unittest discover -s system\verify -p "test_location_collision_blueprint_m343.py" -v
python -m unittest discover -s system\verify -p "test_location_place_registry_m24*.py" -v
python -m unittest discover -s system\verify -p "test_development_kanban_m339.py" -q
python system\studio-plugin\validate_luau.py
python system\verify\verify.py
.\system\studio-plugin\install.ps1
```

Затем **отдельно** проверить в Studio: Game1Bridge запускается; **Plots** на месте; Place Registry Scan работает; `Validate/Capture/Preview/Clear` работают для тестового ассета; `MeshPart` в выделении отвергается; `Workspace.Places` не меняется.

### Защита от потери Plots / Place Registry

Новый `StudioLocationCollisionAuthoring` загружается через `pcall(require)` и не входит в цепочку обязательных require модуля Place Registry. При ошибке его загрузки в Output выводится warning, остальные инструменты Bridge продолжают работу. Это **не заменяет тест запуска в настоящей Roblox Studio и синтаксическую проверку нового Luau**.

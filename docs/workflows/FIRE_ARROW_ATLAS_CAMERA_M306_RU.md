# M306 · Fire Bone Tuner / Arrow Impact / Shared Atlas / Camera Debug

Базовая версия: `game1_diag_2026-11-12_18-26-44.zip` (после M305).

## 1. Fire Bone Tuner
- `Use selected Bone` только считывает `Fire` и `PointLight` на выбранной кости и непосредственно вложенных Attachment. Без эффектов числовые строки отображают `—`, а не создают значения.
- `Create Fire on selected Bone` / `Create PointLight on selected Bone` — явные действия.
- Пресеты сохраняются в `plugin:GetSetting(Game1_FireTuner_UserPresets_v1)`, выбор кости их не меняет.
- Новая Fire использует авторскую ориентацию Tail → Head; *существующие* Attachment/Fire никогда не поворачиваются при выборе.
- Установка Fire Tuner выполняется **отдельно** через `system/studio-plugin/install-fire-tuner.ps1`, с резервным копированием текущей локальной копии. Общий установщик Studio plugin его не заменяет.

## 2. Стрела в любом подвижном объекте
- `BowProjectileService` сохраняет серверные swept-ray, проверку первого касания, урон и headshot.
- `ArrowImpactAttachment` делает невидимую к столкновениям косметическую модель стрелы частью модели цели, отключает массу, коллизии и ставит штатные `WeldConstraint` к движущейся BasePart/root. Никакого нового Heartbeat/Tween для застрявшей стрелы.
- Неподвижный Terrain не имеет BasePart, поэтому стрела остаётся на месте.
- Время жизни оставшейся стрелы — прежние 2,5 секунды.
- Ограничение: Weld следует за `BasePart`, но **не деформируется вместе с отдельными Bone скининга**, если часть тела меняет форму без движения самого MeshPart. Такой скиннинг требует отдельной задачи и Studio-теста.

## 3–4. Общие градации атласов
- Weapons/Arrows — потребители единого `AtlasRegistry` через `game1ConsumerAtlasEditor`, где уже реализованы `deco-atlas-dots`, поисковый список и выбор разрешения.
- `Connect existing atlas` → выбрать опубликованный вариант → выбрать одну из привязанных цветных точек. Unbind и Refresh сохранены.
- `Index existing weapon images` — **отдельное подтверждённое действие**. Сопоставляет локальный SHA256 источника с ранее опубликованным SHA256 и сохраняет существующий Roblox Image ID в общем реестре без Open Cloud, без Studio Sync и без смены активного варианта. Неверифицированные файлы пропускаются с причиной.
- После привязки для применения в Studio нажать **Sync Studio** отдельно для конкретного оружия/стрелы. Выбор варианта не изменяет опубликованный Model ID.
- Публичный API: `/api/texture-atlases/consumer-choice`, `POST /api/texture-atlases/index-existing-weapons` (обязательное `confirm:true`).

## 5. Camera Options ↔ Studio Camera Debug
- Saved camera options — `assets/manifests/options.json`, экспорт — `src/shared/GameOptionsRegistry.luau`.
- В `Options → Camera`: target height, distance, initial pitch, character X/Y, reticle X/Y; именные пресеты (Save/Apply/Delete, максимум 32).
- В Play (Studio) открыть **CAM** рядом с **HS**, изменить числовые значения. Превью живое, играет через существующий `CameraController`; весь боевой reticle и House Sockets читают единое положение точки прицеливания.
- Studio-only remote `CameraDebugChanged` валидирует значения на сервере и помещает JSON-черновик в `ReplicatedStorage.Game1CameraDebug.Payload`. `StudioCameraDraftBridge` передаёт его в локальный Control Center по аутентифицированному API `/api/options/camera-draft`.
- В Options нажать **Import Studio Debug** → поля заполняются **без сохранения** → **Save Camera Options** (или Save preset). Только это меняет манифест и Luau registry. После Save выполняются Rojo Sync и новый Play для применения сохранённых значений к игре.
- Ни Play, ни bridge не пишет в `.control-center` и не вызывает внешние Roblox API. Студийный мост требует работающий Control Center на `127.0.0.1:43821` и разрешённый Studio HTTP.

## Проверить в Roblox Studio (не заменяется статическими тестами)
1. Выбрать кость с существующими Fire/Light: настройки считались и остались прежними; выбрать пустую — новых эффектов не появилось; создать Fire явной кнопкой и проверить Tail → Head.
2. Застрять стрелой в NPC и monster, двинуть персонажа, проверить следование; отдельно проверить фонарь в Landscape Painter.
3. Открыть оружие/стрелу, привязать опубликованные разрешения через цветные точки; импортировать прежний Image ID по явной кнопке; Sync Studio отдельно.
4. В Play нажать CAM, изменить Character X и Cursor X; проверить ретикл, headshot и House Sockets. В Options импортировать черновик, сохранить пресет и Camera Options; перезапустить Play после Rojo Sync.

# M322 · Health UI · Desktop/Mobile Options & Studio Debug

## Цель и границы

Переработан только клиентский слой представления HP и редактор его настроек. Серверные `HP`, `MaxHP`, `LifeState`, регенерация, урон, M317 Hitscan и M320 Monster Aggro не изменены. `OverheadHealthController` по-прежнему единолично решает, **когда** отображать полоски, а `HealthBarView` — **как** их рисовать. `PlayerHealthHudController` отвечает только за верхний экранный HUD. `HealthUiSettings` предоставляет неизменяемую сохранённую конфигурацию с временной локальной накладкой для Studio.

## Параметры в Asset Manager → Options → Health bars

Профили `PC · Desktop` и `Mobile · Touch` сохраняются независимо. Для каждого профиля:

- **Top-screen HP:** `enabled`, `width` (px), `height` (px), `border` (px), `textSize` (px), `top` (px). Начальный desktop — 320×20, mobile — 214×17 вместо 520×37 в M321.
- **Your character overhead:** `enabled`, `width`, `height`, `border`, `nameSize`, `levelSize`, `offsetStuds` — зазор **над видимым верхом рига**, а не над RootCollider.
- **Monster overhead:** те же размеры и зазор, независимо от личной полосы. Имя каждого монстра формируется из `MonsterDisplayName` либо `MonsterSlug` с заглавной буквой у каждого английского слова (`gremlin` → `Gremlin`). Уровень отображается лишь при существующем `Level`.
- **Colors:** отдельные HEX-коды `green` (HP > 65%), `yellow` (30% < HP ≤ 65%), `red` (HP ≤ 30%). Одни пороги действуют для верхнего HUD, собственной и монстровой полоски. Контрастная тёмная подложка, чёрный контур, pill-скругление и Tween остаются.

В том же выбранном профиле — **Debug and test controls → Show debug/test buttons in published TestPlace**. По умолчанию **выключено** для каждого устройства. Скрывает опубликованный test weapon picker; все остальные TL/MV/MO/CS/HS/CAM/HP уже доступны исключительно в `RunService:IsStudio()`. На серверные боевые сервисы, мобильное управление и Roblox CoreGui настройка не влияет.

### Обычный процесс

1. В Studio Play открываем `HP` в верхнем левом блоке Studio Debug. Выбираем `PC` или `MOBILE` и группу SCREEN/SELF/MONSTER/COLORS.
2. Меняем поля: превью применяется сразу; во время превью все живые монстры и своя полоска принудительно видны, чтобы не требовалось начинать бой. Кнопка **Stop preview** возвращает сохранённый профиль. `Reset selected profile` возвращает настройки выбранного устройства к сохранённым значениям.
3. Studio-only remote `HealthUiDebugChanged` (валидация, ограничение частоты, запрет в опубликованной игре) записывает в `Game1HealthUiDebug.Payload` только полный JSON-профиль выбранного устройства. Общий плагин `StudioOptionsDraftBridge` безопасно отправляет черновик в локальный `/api/options/health-ui-draft` через X-Control-Token, так же как черновик Camera Debug.
4. Asset Manager → Options → **Import Studio HP Debug** → **Save selected device profile**. Только эта команда сохраняет `assets/manifests/options.json` и генерирует `src/shared/GameOptionsRegistry.luau`. Перезапускаем Play после Rojo Sync. Черновик не сохраняется автоматически; контроллеры никогда не пишут боевые Attributes.

Схема JSON остаётся `schemaVersion: 1`: добавлены необязательные для старых манифестов группы `healthUi.desktop/mobile` и `debugUi.desktop/mobile`. На первом открытии недостающие группы заполняются настройками по умолчанию и выгружаются в Lua реестр. Обновление одного устройства не меняет профиль второго. На сервере Control Center при записи проверяются границы размеров, конечность всех чисел, HEX-коды и флаги; неизвестные ключи отклоняются. Для отката достаточно вернуть предыдущие `assets/manifests/options.json` и `src/shared/GameOptionsRegistry.luau` из Git, затем перезапустить Control Center / Rojo Play.

## Проверка перед применением

- `python system/verify/verify.py`.
- `node --check system/control-center/static/options.js`.
- `python system/studio-plugin/validate_luau.py`.
- `python -m unittest discover -s system/verify -p 'test_m322*.py' -v`.
- `git apply --check` на M321.

Реальное положение над деформированным skinned MeshPart, предпросмотр с мобильной эмуляцией и плагины в Roblox Studio Play нужно обязательно проверить вручную: статические тесты не рендерят Roblox UI.

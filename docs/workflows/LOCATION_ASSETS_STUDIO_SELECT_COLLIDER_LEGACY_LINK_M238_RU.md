# M238 — Select in Studio, COL atlas, historical Model linking

Поверх M237. Один Location Asset (`slug`) за операцию, никаких публикаций Roblox Model или Atlas во время Find / Select / Link / Sync.

## Исправления интерфейса

- `Find Mesh IDs · Studio`: только считывание Mesh ID / актуальных текстур для визуальных частей. Не меняет выделение Studio или Place.
- Каждая строка содержит **Select in Studio**: выделяет именно Model, к которой принадлежит найденный MeshPart (для управляемых — зарегистрированный root; для внешних — ближайшую Model). Это не отметка для синхронизации.
- Галочка **For Sync** относится только к управляемой строке. **Mark all for Sync**, **Sync selected** и **Sync all** — отдельные действия. `Sync` только после подтверждения.
- После `render()` сохраняются позиции прокрутки модального окна и внутреннего списка MeshPart.
- Внешние совпадения по старым ID показываются без умолчания `Already up to date` для всего Place. Для них выводится причина недоступности непосредственного Sync.

## COL и DoubleSided

- COL-меши (`col_mesh`, `COL_*`, `*_col`, `*_col_*`) — **только физика**. Нет статуса Texture, нет Texture/ColorMap ID, нет проверки атласа и нет Atlas Update на COL. Старые мусорные TextureID на ранее размещённых коллайдерах не трогаются при Find или текстурном Sync.
- Новая публикуемая Model-копия очищает TextureID и SurfaceAppearance на COL без изменения исходного FBX.
- `DoubleSided=false` — общий **дефолт для новых/отсутствующих настроек** Location Assets и Real Estate: Python policy, общий редактор, реестр Real Estate, Studio и Runtime. Явно сохранённые `true` и `false` сохраняются. Никакой миграции с перезаписью существующих параметров.

## Внешние исторические модели

Метка отсутствует — прежний ID меша сам по себе не разрешает замену. На историческом совпадении **Select in Studio** доступна всегда. Кнопка **Link historical model** отображается только когда *весь MeshPart inventory ближайшей целой Model* однозначно совпал с **одной старой опубликованной Model** ассета и отсутствуют признаки владения другими ассетами.

**Link** требует подтверждения и повторно проверяет текущее дерево, идентификаторы, CFrame/Scale и полную структуру управляемой геометрии по иммутабельной старой публикации. При успехе дописываются `Game1DecoAssetSlug`, Instance ID и старый Model ID, но **не меняются ни геометрия, ни текстура**. Link записывается в Studio Sync Audit как `model_reference`. После него делается новый Find: новый управляемый instance будет иметь `Mesh pending` и сможет получить явный обычный `Sync` с использованием общего `StudioManagedRigSwap`. Корневая Model не удаляется.

Если набор Mesh ID совпал с несколькими публикациями, структура отредактирована или обнаружен чужой владелец — привязка недоступна. Не нужно переименовывать FBX или пробовать замену наугад.

## Контракты и безопасность

- Studio Bridge протокол **8**: `scan`, `select`, `attach`, `replace`.
- `select`: `scanToken` + `partKey`, только `Selection:Set({Model})`, токен не расходует, ни AtlasRegistry, ни audit не меняется.
- `attach`: `scanToken` + `partKey`, только проверенный внешний исторический root, полный preflight до записи, undo waypoint и rollback метаданных, единичный токен, запись в аудит, **не** `mark_synced`.
- `replace`: `scanToken` + `selectedKeys`, только управляемые pending MeshPart, без смены старого протокола замены дочернего rig.
- Перезаписей БД, изменений схемы SQLite или автоматической публикации нет.

## Проверки

Профильные `unittest`, Node DOM-light проверки, `verify.py`, Luau preflight, JS syntax. Реальный Roblox Studio Edit Mode (включая Link конкретного `christmas_tree`) и Play не проверялись в дампе; для первого запуска использовать копию Place.

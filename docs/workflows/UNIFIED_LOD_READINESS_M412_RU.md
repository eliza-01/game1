# M412 · Единый LOD readiness: Location Assets и Real Estate

**Доменный интерфейс:** `LOD Manager → 02 · LOD readiness` с вкладками `Location Assets` и `Real Estate`. Вторая секция `04b · House Streaming` удалена. `02` владеет **House Streaming Profile (off / full / lod1)**, публикацией LOD-частей и индивидуальными дистанциями каждой части. Начиная с M414, `Real Estate` сохраняет только авторинг FULL и физику; дистанции там не задаются. Общих дистанций LOD1 / выгрузки для дома нет. Гистерезис = 10 studs как единая техническая настройка общего стримера.

## Единый механизм

- **LOD Model ID**, staging, публикация, проверка SHA256, optimistic revision и повторное использование: `services/model_lod_common.py`, `services/lod_reuse_catalog.py`. Доменные хранилища отвечают только за ключ ресурса, SQLite и происхождение.
- Runtime Place: существующий `RuntimePlaceBuilder` / `house_runtime_compilation` помещает *проверенные* LOD Model ID в описания визуальных частей.
- Клиент: один `LocationWorldStreamer` и один общий лимит операций. `HouseVisualAdapter` остаётся адаптером геометрии домов, а не отдельным стримером. Все FULL/LOD1/UNLOADED переходы используют общую `LocationLodDistancePolicy`.
- Дома: **независимый LOD1 у выбранных визуальных MeshPart**. `house_level5_01/roof` и `house_level5_01/walls_outside` — независимые слоты. Все части видны в LOD Manager. Достаточно хотя бы одной опубликованной части; каждая часть с LOD1 переключается независимо по своему порогу, а части без LOD1 остаются FULL до собственной границы выгрузки. Общего исчезновения частей нет. Историческая запись `real_estate_lod1` сохраняется для истории; Runtime не использует её.
- Избранный чужой LOD1 фиксируется конкретным Model ID + ревизией и не меняется при публикации новой версии источника. Никакой повторной загрузки FBX ради reuse.

## Цвет и материалы

Geometry-only LOD1 клонируется отдельно для каждой части. `RuntimeVisualAppearance.Apply` получает **те же** Material, Color, Atlas и Alpha, что FULL этой части. Стены/крыша/труба не объединяются в один меш, их материалы остаются независимыми. Чтобы текстура выглядела корректно, UV выбранного LOD1 должны соответствовать используемому атласу, а pivot и пропорции — FULL-части.

**Граница:** динамическая перекраска дома конкретным игроком после запуска игры пока не является отдельной реализованной сетевой системой. M412 сохраняет раздельные настройки частей и готовую структуру для дальнейшей авторитетной передачи персональных цветов; не обещает клиентское изменение цвета, которого ещё нет.

## Контракт и миграция

- `real_estate_part_lod1` — новая таблица `(house_slug, part_name)`; ревизии, published Model ID, source SHA и источник reuse.
- `real_estate_part_lod1_history` — публикации. `real_estate_part_distances` (M414) — индивидуальные пороги по (house_slug, part_name) с ревизией. Миграция аддитивная; перед изменением SQLite — backup.
- Устаревшие цельные LOD1 не конвертируются автоматически в LOD частей: это неверное отображение геометрии и окраски. Профиль `lod1` требует хотя бы одну опубликованную LOD1-часть. Часть без опубликованной LOD1 остаётся FULL до своего `Unloaded from`; незавершённые или устаревшие LOD-ревизии блокируют Preflight.
- Неизменённые Plot bindings, FULL-модели, риги, двери, коллизии, сокеты и текстуры. Исторические `loadDistanceStuds` переносятся в новые per-part LOD-пороги и убираются из Real Estate.
- Для каждой части в LOD Manager: `LOD1 from`, `Unloaded from`, `Save distances`; `Choose FBX` с именем `<house_slug>_<part_name>_lod1.fbx`, `Stage`, `Publish` или `Use published LOD1`. Без LOD1 — FULL → UNLOADED.
- Публикация DEV не разрешается автоматически (`publishAllowed=false`). Требуются новый Preflight, Runtime Draft, Studio Play и мобильный тест.

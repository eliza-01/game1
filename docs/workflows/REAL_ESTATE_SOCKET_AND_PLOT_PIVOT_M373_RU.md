# M373 · Канонические сокеты домов и независимые Plot pivots

## Тип дома и точка участка

- Тип: `house_level<L>_<VV>`, например `house_level5_01`: `L` — уровень, `VV` — вариант, а не номер публикации Roblox. У нового Asset ID тот же тип.
- Позиция: `(plotIndex, houseLevel, houseVariant, spawnPivotLocalCFrame)`. CFrame сохраняется относительно `plot_NN_volume`. Это **не внешняя ссылка на модель**: удаление дома и повторная регистрация того же уровня/варианта не сбрасывают позицию.
- Для существующего Studio Bridge поле `houseSlug` сохраняется как сериализация `(level, variant)`, а не FK на зарегистрированный дом. `spawnPivotLocalCFrame` равен сохранённому `localCFrame`.
- Всегда используем авторский **проектный pivot** `house_armature`, совпадающий с pivot всех MeshPart. Никаких привязок к именованному MeshPart `house` или центру bounds.
- `land_spawn_01_socket` из старого рига не является Plot pivot. Точка участка принадлежит участку, а не костям дома.

## Сокеты `house_armature`

Один скелет, lowercase ASCII snake_case, индексы из двух цифр (для 10+ могут быть длиннее); все перечисленные точки опциональны, за исключением сокетов реально используемой функциональности.

| Назначение | Имя / шаблон | Примечание |
|---|---|---|
| Точка этажа | `house_floor_<NN>_spawn_socket` | Например `house_floor_01_spawn_socket`; без старого `_spawn_01_socket`. Обязательна для доступного лифтом этажа. |
| Кнопка лифта | `elevator_<NN>_socket` | Например `elevator_01_socket`, не является местом назначения |
| Ось двери | `door_<NN>_hinge_socket` | Дверь и ручки могут быть отдельными MeshPart, со 100% весами на соответствующий hinge |
| Ручка | `door_<NN>_handle_inside_socket`, `door_<NN>_handle_outside_socket` | Дочерние кости door hinge; без собственных skin weights |
| Замок | `door_<NN>_padlock_<NN>_inside_socket`, `door_<NN>_padlock_<NN>_outside_socket` | Дочерние кости hinge. Имя без стороны — устаревшее и не используется |
| Сундук | `chest_<NN>_socket` | Пример `chest_01_socket` |
| Дымоход | `chimney_<NN>_socket` | Пример `chimney_01_socket` |
| Камин | `fireplace_<NN>_socket` | Пример `fireplace_01_socket` |
| Растения | `houseplant_01`…`houseplant_09`, `houseplant_010`…`houseplant_015` | Формат в исходном `.blend`; **без** `_socket`. |

Остальные MeshPart произвольны по имени. Статические меши без весов, движущиеся дверь и ручки на hinge. Новые сокеты должны быть реально переименованы в Blender до FBX публикации; изменение Lua не меняет костей внутри FBX.

## Общие материалы

На каждый MeshPart по умолчанию `Material + Color`; Atlas назначается опционально и персонально. `Alpha transparency` выключен по умолчанию; только явно включённая опция допускает `SurfaceAppearance`. Наличие альфа-пикселей в исходном PNG ничего не включает само собой. Политика централизована в `StudioTextureAppearance` для всех разделов.

## Коллизии

`col_mesh` не публикуется и не используется. Отдельный Collision Blueprint дома будет использовать Roblox Parts по схеме Location Assets. Коллизии не зависят от названий декоративных MeshPart или от сокетов.

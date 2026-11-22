# M423 · Real Estate · настройки LOD и публикация FBX

## Границы ответственности

- **LOD Manager → Real Estate**: только режим стриминга дома, пороги FULL → LOD1 и UNLOADED в studs на каждую визуальную часть, статус опубликованного LOD1 и готовность к Preflight. Сохранение через существующие `runtime-profile` и `parts/{part}/distances`, с `expectedRevision`. Смена настроек инвалидирует текущий Preflight.
- **Real Estate → Registered Library → Manage mesh → LOD1 · FBX**: выбор и stage отдельного `{house_slug}_{part_name}_lod1.fbx`, переиспользование опубликованной геометрии из общего каталога, публикация Model ID. Используются существующие `lod1-stage`, `lod1-reuse`, `lod1-publish` endpoints без дублирования авторинга.
- **Model · FBX / Texture · atlas** остаются ответственностью Real Estate. **Location Assets** и серверный runtime/streaming не изменялись.

## Навигация и визуальная структура

Дома отображаются отдельными раскрываемыми карточками. Внутри каждой карточки — режим и статус готовности, а затем группы `Основа`, `Стены и конструкции`, `Крыша и проёмы`, `Интерьер и декор`, `Другие части`. Неизвестные авторские имена MeshPart автоматически попадают в последнюю группу и не теряются. Каждая часть получает собственную карточку с текущим маршрутом визуализации, Model ID, порогами и явным сохранением. Группы раскрываются независимо; состояние раскрытия домов и групп сохраняется между обновлениями списка в рамках открытой страницы.

Поиск принимает slug дома и имя MeshPart; фильтр показывает все/готовые/требующие проверки дома. Кнопка `LOD1 FBX · Real Estate` открывает соответствующий редактор части дома. Выбор модели никогда не производится из LOD Manager.

## Проверка и ограничения

- Проверить `node system/verify/lod_real_estate_settings_m423.js`, `node system/verify/lod_readiness_domains_m412.js`, `node system/verify/lod_house_part_distances_m414.js`, `node system/verify/real_estate_mesh_publication_m413.js`, `python system/verify/verify.py`.
- Смена ID/ревизии публикации, расстояний, Model/Atlas и данные SQLite не мигрируются.
- Browser/UI сценарии нужно подтвердить в живом Control Center после установки. Проверка Studio Play не требуется для перемещения UI (runtime Luau не менялся).

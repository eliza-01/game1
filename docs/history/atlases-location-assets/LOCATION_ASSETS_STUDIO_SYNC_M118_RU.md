# M118 · Location Assets → Sync Studio

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


## Контракт

Location Assets не являются шаблонами ServerStorage. Публикация хранит
Model/Image Asset IDs, а DecoManager читает их из `/api/location-assets`.

`POST /api/location-assets/studio-sync` выполняет один `deco-refresh` запрос
через локальный Game1Bridge. Plugin заново получает весь каталог, применяет
`DecoPlacedAssetSync.RefreshTextures` к уже размещённым моделям в
`Workspace/Game1DecoAssets` и возвращает `{studio:{models,parts,registryItems}}`.
Значения `models` и `parts` — число действительно изменённых объектов,
не число опубликованных/размещённых объектов. `0` — нормальный результат,
если материалы уже актуальны или пока нет размещённых моделей.

Для будущего размещения новых ассетов используется обычный DecoManager.
Команда не импортирует модели в `ServerStorage`, не меняет сохранённое
расположение/масштаб моделей, не перепубликует Roblox Assets, не изменяет
SQLite, FBX и Asset IDs. При неработающей Studio возвращает явную ошибку.

## Безопасность и восстановление

- Команда доступна только через существующие HTTP-авторизацию Host Agent и
  loopback Studio Bridge (токен, уникальный operationId, schemaVersion=1).
- Команда отправляется только при Studio Edit Mode; при Play/Run истекает
  ожидание и не сообщает о ложном успехе.
- Изменения в Workspace являются обычными Studio-изменениями с waypoint.
  Сохранение place управляется Studio/DecoManager, а не Asset Manager.
- При отсутствии данных исходной текстуры альфа-режим остаётся неизвестным:
  старый `SurfaceAppearance.AlphaMode` не переписывается (правило M117).

## Проверка

После установки плагина M118, перезапуска Studio и Host Agent выбери
Location Assets → **Sync Studio**. Убедись, что в Studio открыт нужный
Place в Edit Mode. Для теста размещённого PNG с альфой проверь
`MeshPart.SurfaceAppearance.ColorMap` и `AlphaMode=Transparency`.
Повтори Sync — он должен сообщить `0` изменённых частей.

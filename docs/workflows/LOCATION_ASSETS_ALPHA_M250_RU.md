# M250 · Location Assets — отдельная настройка Alpha

## Назначение

Alpha является **свойством конкретного Location Asset**, а не общего атласа.
Один и тот же Image ID допускает разные режимы отображения у разных потребителей.
`alphaEnabled = false` (по умолчанию) соответствует `SurfaceAppearance.AlphaMode = Opaque`:
альфа-канал `ColorMap` игнорируется. `true` соответствует `Transparency`:
альфа-канал формирует прозрачность. Не следует заменять `Opaque` на `Overlay`:
`Overlay` показывает `MeshPart.Color` через прозрачные пиксели, а не игнорирует альфу.

## Границы модулей

- `services/location_asset_alpha.py`: строго валидирует булево значение и выполняет
  атомарное обновление по `expectedRevision`; не обращается к Atlas Registry/Open Cloud.
- `LocationAssetStore`: SQL v6, idempotent migration с SQLite backup,
  `alphaEnabled` в API, JSON и generated Luau. `register()` сохраняет настройку
  при редактировании FBX/метаданных; переименование slug не сбрасывает поле.
- `POST /api/location-assets/{slug}/appearance`: отдельная авторская ручка
  `{alphaEnabled:boolean,expectedRevision:int}`. Не меняет Model/Image IDs.
- `location-asset-workflow.js`: чекбокс в `Edit → Texture · atlas`, отдельная
  кнопка Apply Changes; альфа сохраняется независимо от публикации пикселей.
- `StudioTextureAppearance.ApplyAlpha/ApplyLocation/Capture/Restore`: общий
  Studio-механизм с откатом. Реализация Real Estate продолжает вызывать
  старый `Apply` с существующей политикой `Overlay/Transparency`.
- `DecoAssetLoader`, `DecoPlacedAssetSync`: новые размещения и `Find → Sync`.
- `Place Registry`: обнаруживает `needsAlpha`, invalidates scan digest при
  смене настройки, поддерживает одиночный и групповой Sync с журналом/Undo.

## Правила применения

1. Только **визуальные** MeshPart зарегистрированного Location Asset.
2. COL-меши и `Game1DecoPhysicsOnly` исключены: Alpha не меняет физику,
   прозрачность BasePart, MeshId, Size, CFrame, Texture ID или коллизию.
3. Если у визуального MeshPart нет SurfaceAppearance, Studio Sync создаёт
   его с текущим ColorMap, иначе меняет только AlphaMode. Новые публикации
   изображений не выполняются.
4. Перед записью сохраняется реальное состояние SurfaceAppearance и TextureID.
   Ошибка приводит к откату; авторские изменения выполняются только явным Sync.
5. В ревизиях Place Registry сохраняется `AlphaMode` для восстановления истории.
6. После смены Alpha старый Scan нельзя использовать для новых мутаций.

## Проверка

1. На копии Place выберите альфа-атлас и включите Alpha у одного ассета,
   оставив его выключенным у второго потребителя **того же Image ID**.
2. Убедитесь, что `Model ID`, `Image ID` и `bindingRevision` не изменились.
3. Выполните `Find Mesh IDs`: должно появиться `Alpha требует Sync` даже при
   актуальных Mesh/Texture ID. Проверьте одиночный `Sync` и `Sync group`.
4. У визуальных MeshPart должен стать `AlphaMode=Transparency`; у COL не должно
   появиться SurfaceAppearance. Выключите Alpha и синхронизируйте повторно:
   ожидается `Opaque`.
5. Проверьте отмену через историю Roblox Studio / журнал Place Registry.
   Для полного резервирования по-прежнему нужен `.rbxl`.

**Непроверено в этом окружении:** реальное изменение AlphaMode через Roblox
Studio Plugin на конкретной публикации. В некоторых версиях Studio режим
`Opaque` может требовать включённой beta-функции. Не выполняйте массовый Sync,
если Studio возвращает ошибку записи AlphaMode; не используйте `Overlay`
в качестве незаметного запасного варианта.

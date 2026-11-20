# M399 · Automatic Location Runtime coverage

**База:** M398. Runtime Studio/DEV не проверен. `publishAllowed=false` остаётся.

- У каждого **зарегистрированного типа Location Assets, присутствующего в проверенном Scan**, режим по умолчанию — `Auto` (эффективно `FULL → Hide`). Новый slug не требуется добавлять вручную в `location_streaming.json` или код загрузчика.
- `modes` теперь хранит **переопределения политики**, а не allowlist: `lod1`, `lod2`, `full`, `off` и явное `auto`. Профиль LOD1/LOD2 выбирается владельцем, только при опубликованной модели. `Off` означает намеренное отключение, а не значение по умолчанию.
- Реальные размещения определяет только Place Registry. Composite, включая `rig_carrier`, дополнительные MeshPart, кости и эффекты, использует **тот же** `location_runtime_composite` и `LocationWorldStreamer`, что и раньше; отдельных обработчиков `lantern_*` / `torch_*` нет.
- Неопубликованный, нераспознанный или структурно несовместимый объект выбранного типа **останавливает Preflight**, а не silently остаётся полноразмерным в Workspace. Это не разрешает обход коллизий `PreciseConvexDecomposition`: сначала исправить физический контракт.
- Real Estate не меняется: у домов собственные Streaming Profiles и серверные компоненты.
- Публикация DEV разрешается только после реального Scan → Sync → сохранения исходного RBXLX → Preflight → Build и проверки в Roblox Studio / на мобильном устройстве.

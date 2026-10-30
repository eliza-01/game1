# M147 · House sockets / Studio debug hotfix

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


База: **M146**, применение сверху. Существующие модели, Asset IDs, SQLite, Host Agent, Studio Bridge не меняются.

- `HS` — отдельный Studio launcher рядом с `TL`, доступен независимо от Test Loadout remotes; в TL сохранена кнопка `HOUSE SOCKETS · DEBUG` к тому же единственному окну.
- Debug remotes ищутся при нажатии, поэтому окно открывается даже если серверный debug-сервис не стартовал. Ошибка видна в самом окне.
- Сервер выводит число управляемых домов, обнаруженных socket и ProximityPrompt после инициализации. У домов с частично восстановленными костями предупреждения остаются.
- Новые Attachment с именами из контракта инициируют отложенный повторный поиск сокетов только в затронутом доме.
- Runtime Location Assets не читает/пишет `SurfaceAppearance.ColorMap/AlphaMode` без Plugin capability. Текстуры/AlphaMode для опубликованных SurfaceAppearance — обязанность Studio Sync. MeshPart без SurfaceAppearance по-прежнему обновляет TextureID.

Проверить вручную после Rojo sync и перезапуска Play: лог `[game1][house-socket] ready`, кнопку `HS`, список найденных точек, F-подсказку и дверь. Визуал/доступность реальных костей зависит от опубликованных моделей.

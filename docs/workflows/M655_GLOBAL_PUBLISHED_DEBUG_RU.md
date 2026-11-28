# M655 · Global Published Debug

**M655 · Global Published Debug.** `Options → Debug / TestPlace → Enable debug / test buttons`: одна глобальная галочка `debugUi.showPublishedControls`, независимо от Place ID, устройства, владельца и ранга. Все подключённые игроки опубликованного Place (включая compiled Runtime) при ON получают server-owned authorization; OFF не запускает опубликованные debug-сервисы и блокирует debug-вызовы. Studio и отдельные Studio-only инструменты GP/AG/Buffer сохраняют прежний контракт. Перед публичным релизом выключить debug: ON предоставляет тестовые полномочия всем игрокам. Миграция прежних PC/Mobile flags — OR, Place ID удаляется; default OFF для новой конфигурации. Нативная Published-приёмка открыта. Приоритет: диагностика регрессии GPU/CPU (владелец сообщил 25 → 125 ms GPU в покое), не снижение качества. Причина пока неизвестна. См. `docs/workflows/M655_GLOBAL_PUBLISHED_DEBUG_RU.md`.

## Контракт

- OptionsStore — единственный writer: persisted migration на запуске Control Center, затем строгая глобальная схема, старые API writes отвергаются. Миграция сохраняет Start in Hub, Started language, locale и другие опции. Если старая галочка была включена хотя бы для одного устройства, глобальная включена.
- PublishedDebugAccess — единая проверка глобальной настройки для клиента и сервера; сервер продолжает выставлять атрибут разрешения при входе и проверять его на debug remotes. Никаких Place ID / device gates. Профиль размещения кнопок по устройству не изменён. GP/AG/Buffer и действия Studio Edit остаются Studio-only.
- После Save: Rojo Sync обновлённого Place; если используется compiled Runtime draft, пересобрать из актуального авторского Place. Publish и новый сервер; уже работающие серверы не меняют конфигурацию.
- ON даёт всем подключённым игрокам тестовые возможности, включая test loadout/weapon chooser, поэтому не использовать на публичном production-релизе. OFF относится к опубликованной игре, Studio доступен по прежним правилам.

## Приёмка

- Проверить ON/OFF, два аккаунта, ПК и телефон, authoring / compiled Runtime; LD открывается, Start capture собирает отчёт при доступном Runtime manifest, OFF скрывает кнопки и сервер не принимает debug remotes. Native NOT_RUN.
- Регрессия GPU/CPU: фиксированное качество, одна позиция/камера, холодный и тёплый вход; LD + MicroProfiler при скачке. Сопоставить время кадра и изменения геометрии, skinning, света, частиц, памяти и очереди LOD. Не считать 25 → 125 ms измерением, проведённым в контейнере; это наблюдение владельца. Не менять пороги и качество без evidence.

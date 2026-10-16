# M101 — Studio Timeline: разделение обязанностей

## База

Архив `game1_diag_2026-10-16_10-23-07.zip` + M99 + M100 + `game1_m100_control_center_stale_assets_hotfix.patch`.
M101 касается исключительно Studio Bridge, его тестов и проверки сборки плагина. Серверная/клиентская игровая логика не меняется.

## Владение

- `Game1Bridge.server.luau`: композиция и HTTP-polling команд только в Edit Mode; не хранит состояние Timeline.
- `StudioTimelineEditorCommands`: единственный владелец открытой сессии, eventCatalog/events, scrub-position, подтверждения и ответа `timeline-editor-result`.
- `StudioTimelineWidget`: создание DockWidgetPluginGui, кнопок, ViewportFrame/WorldModel и контролов без HTTP и загрузки ассетов.
- `StudioTimelinePreview`: владение временной моделью предпросмотра и камерой, загрузка Roblox model asset/KeyframeSequence с прежними ограниченными retry; очистка по следующей сессии.
- `StudioTimelinePoseSampler`: сопоставление Pose с Bone/Motor6D, интерполяция CFrame с EasingStyle/EasingDirection. Не зависит от UI или HTTP.
- `StudioTimelineTransport`: два исходящих HTTP POST к Host Agent и Studio Bridge с прежними токенами и обработкой ошибок.

## Совместимость

Сохраняются `Game1AttackTimeline_v2`, `TimelinePreviewWorld`, `Game1TimelinePreview`, формат `schemaVersion=1`, команды `ready` / `set-event`, endpoint `timeline-editor-result`, scrubbing и Mouse LMB orbit/wheel zoom.
В предпросмотре модели остаются в `WorldModel`, а не в `Workspace`.
**Не менялись** алгоритмы pose interpolation, тайминги, правила публикации, runtime атаки и мультихиты.

## Проверка и риски

`verify.py`, полная регрессия Python, проверка `git apply --check` и обратного отката на копии указанной базы. Автотесты контролируют упаковку Rojo и ключевые контракты исходников; это не проверка исполнения Luau в Roblox Studio.

После установки плагина вручную в Studio проверить открытие Timeline из Asset Manager, загрузку опубликованной модели и KeyframeSequence, скраббинг с Bone/Motor6D, выбор Hit, подтверждение точки, вращение/зум камеры и возврат результата в Asset Manager. Отдельно — отсутствие доступа к Roblox asset и сообщение об ошибке при неверном ID.

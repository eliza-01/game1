# M96 — Декомпозиция AnimationSpeedScaling

**База:** `game1_diag_2026-10-16_09-01-01.zip` (после очистки неудачной навигации M95). Только рефакторинг без изменения поведения.

- `AnimationScalingFormula` — чистый расчёт; не знает о Workspace, Model, реестрах, Roblox-сервисах. Два API намеренно различаются: `RulePercent` сохраняет историческое ограничение делителя только снизу, `DetailsPercent` использует нормализованные authored/debug units.
- `AnimationScalingPolicy` — поиск опубликованных профилей, идентификация humanoid/monster и авторские clip-правила; не обращается к Workspace.
- `AnimationScalingDebugOverrides` — чтение локальных Studio/debug атрибутов. Для пользовательских клипов принимает **только number > 0**; отрицательные, NaN и нечисловые значения не становятся правилами.
- `AnimationSpeedScaling` — совместимый фасад: сохраняет публичные поля, сигнатуры, приоритет `Workspace clip override > published clip custom > profile`, формат ResolveDetails, RefreshPlaying и его условие `track.Speed > 0`. Controller/Animator владеют playback. Нет новых Heartbeat, per-actor tasks, RemoteEvents или экземпляров.

## Тесты / пределы

`python system/verify/verify.py` + `python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q`.
Дополнительные контрактные тесты M96 проверяют публичный API, владение зависимостями, приоритет правил и исполнение **производственного** pure-Luau math модуля через `luatex`, если доступен (при отсутствии тест только пропускается).

Ручной Studio Play smoke: Character/NPC/Monster run/walk/attack/combat_idle в тех же процентах; тест для одного опубликованного custom clip и Studio-override; изменение debug units у играющего трека; сравнить отсутствие ускорения на idle без правила. **Реальный Roblox Animator этим патчем не проверяется.**

Нет миграций SQLite, изменений публикаций/Asset ID, сетевых контрактов, клиентских контроллеров, AI, столкновений или плагина.

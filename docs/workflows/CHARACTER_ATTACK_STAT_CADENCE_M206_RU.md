# M206 · Gameplay-owned Character AttackSpeed cadence

## Причина

Раньше `AttackSpeed` масштабировал скорость клипа, поэтому длительность удара
получалась `timeline.duration / (AnimationSpeedScaling.percent / 100)`. При
одинаковой характеристике длинный FBX `human_female` (≈1.867 с) и короткий
`human_male` (≈1.467–1.5 с) имели разные игровые периоды атак, несмотря на
одинаковые значения характеристики.

## Целевой контракт — игровые персонажи

- `src/shared/combat/CharacterAttackCadence.luau` — единственный источник
  арифметики. Нормализованный `AttackSpeed` в диапазоне 25–400; базовые
  **3 секунды при AttackSpeed=100**, то есть `attackPeriod = 300 / AttackSpeed`.
  Опорное значение выбрано по фактическому старому male 1HS (1.5 с / 0.5).
- `AttackTimelineConfig.ResolveCharacterRuntime(clipId, AttackSpeed)` преобразует
  длительность источника в **скорость playback**, а не в длительность атаки:
  `playbackDuration = attackPeriod - EndGuardSeconds`,
  `playbackSpeed = sourceDuration / playbackDuration`.
- Нормализованные события HitStart/HitEnd сохраняют авторские пропорции:
  `eventSeconds = normalizedTime * playbackDuration`. У разных клипов события
  могут наступать на разных долях общего периода; это осознанный контракт.
- **И клиент, и сервер** вызывают эту функцию. Сервер остаётся владельцем
  допуска нового удара, его срока и окна повреждений.
- Character AnimationController больше не использует custom/per-clip
  AnimationSpeedScaling для атак. Эти настройки сохраняются для locomotion,
  death и других каналов; NPC и Monster по-прежнему используют старый
  `AttackTimelineConfig.ResolveRuntime` с их собственными правилами.
- Поворот при прицеливании больше не зависит от индивидуального множителя
  проигрывания FBX. UpperBodyComposer и bounce используют фактический
  `playbackSpeed` конкретного клипа.

| AttackSpeed | Игровой период | Время проигрывания клипа (без guard 0.03 с) |
|---:|---:|---:|
| 100 | 3.00 с | 2.97 с |
| 200 | 1.50 с | 1.47 с |
| 400 | 0.75 с | 0.72 с |

Существующие таймлайны не меняются, данные Asset Manager не мигрируются.
Любые опубликованные Animation Asset ID остаются прежними.

## Границы и проверки

`M206` меняет только игровой ритм персонажей; это **изменение баланса**.
Параметры базового темпа регулируются в CharacterAttackCadence, а не
индивидуально для пола или clip ID. Серверное событие `AttackIntent` не
принимает предлагаемую клиентом длительность.

Тест `system/verify/test_character_attack_cadence_m206.py` проверяет арифметику
против реальных длительностей из манифеста, наличие общего client/server
резолвера, сохранение нормализованных окон и неизменность NPC/Monster путей.
Это контракты и модельные вычисления, не эмуляция Roblox AnimationTrack.

**Обязательно проверить в Studio Play**: при одинаковом AttackSpeed у
human_male/female длительность анимации и AttackEndsAt совпадает; при удвоении
характеристики длительность вдвое меньше; кадры HitStart/HitEnd соответствуют
текущему Timeline Editor; не происходит раннего выхода upper-body, прерывания
атаки или несогласованности между сервером и клиентом при изменении экипировки
во время атаки. Выходной `EndGuard` — не окно урона.

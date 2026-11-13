# M329 · Дальность HP монстров и общий Workspace streaming

## Результат

- `Options → Health UI → PC / Mobile → Monster overhead → Name + HP visibility radius`: по умолчанию **100 studs**, независимо для ПК и телефона.
- Радиус измеряется по трёхмерной дистанции **от RootCollider игрока до RootCollider монстра**; не от камеры. Порог применяется к имени, уровню и полоске здоровья одновременно, вне зависимости от прицеливания, агрессии или Studio HP Debug preview.
- Клиент переоценивает видимость раз в 0.10 секунды, а не каждый кадр. Серверные HP, коллизии, aggro, дамаг и дальность атаки не меняются.
- `Options → World streaming target` хранит **одно общее** целевое значение радиуса для Place (по умолчанию **150 studs**). В Options находится кнопка **Copy Studio Command Bar code**. Сохранение значения в Asset Manager не применяет настройку Workspace в живой игре.

## Ограничения Roblox и почему нет разных радиусов Terrain для PC / Mobile

`Workspace.StreamingTargetRadius` — свойство **Place**, не игрока. Roblox не предоставляет документированного API для независимого целевого радиуса подгрузки Terrain и MeshPart в одном Place отдельно для каждого клиента. Также движок может удерживать ранее подгруженные объекты за пределами целевого радиуса. Это **не точный clipping distance** и не гарантирует отсутствие всех видимых MeshPart/Terrain за 150 studs.

Вместо покадрового скрытия геометрии, который нарушил бы мир/боевые коллайдеры и добавил нагрузку, используются нативные настройки Streaming Roblox. Опция общей дальности специально **не выдается** за пер-device настройку.

## Порядок применения

1. Применить патч и открыть Asset Manager. Старые индивидуальные размеры, цвета и отступы HP автоматически дополняются полем `maxDistanceStuds` без сброса значений.
2. В Options выставить `Monster overhead → Name + HP visibility radius` для PC и Mobile, сохранить **каждый профиль отдельно**.
3. В Options выставить `World streaming target = 150`, Save.
4. Нажать Copy Studio Command Bar code, перейти в **Studio Edit** открытого **Eyesland Dev** и вставить команду в Command Bar. Проверить вывод. Если какое-то свойство недоступно Command Bar, выставить его в `Workspace → Properties → Streaming` вручную. Должны быть: `StreamingEnabled = true`, `StreamingMinRadius = 64`, `StreamingTargetRadius = 150`, `ModelStreamingBehavior = Improved`, `StreamOutBehavior = Opportunistic`.
5. Синхронизировать Rojo (для HP) и **Publish to Roblox** (для Workspace), затем перезапустить TestPlace.

Уменьшенный StreamingTargetRadius может делать дальние декорации и мосты видимыми позже; для большого мира Roblox рекомендует целевой радиус 1024 по умолчанию, 150 — явный выбор для экспериментальной оптимизации. Профиль следует проверять и на ПК, и на реальном мобильном устройстве.

## Тесты

- `python -m unittest discover -s system/verify -p "test_m329_*"`
- `python -m unittest discover -s system/verify -p "test_m322_*"`
- Ручные: дистанции 99/101 studs, прицеливание за радиусом, агро за радиусом, смена PC/Mobile, профили с разными значениями, ракурс камеры. Для streaming — выход из зоны 150, повторное приближение и переход между крупными локациями.

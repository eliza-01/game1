# M638 · MNPC Runtime visual LOD / red dummy

> Исторический отчёт. Актуальный серверный режим и переключатель описаны в [M639](M639_MNPC_RUNTIME_DEMAND_RU.md); M632 pilot заменён.

Решение владельца: отсутствие опубликованных LOD1 не блокирует Runtime. В LOD1 используется один красный статический Part (габарит RootCollider, fallback 2×4×2 studs), а не новый анимированный Roblox Dummy. Без костей, Animator, столкновений, touch/query и тени. Существующий корень сохраняет движение/поворот. Проверенный опубликованный MeshPart автоматически заменяет заглушку, когда локальный prototype готов; Model Asset ID никогда не используется как Mesh ID.

## Реализовано

- Общий `MnpcLodController` для реплицированных `Monsters` / `NPCs`: дистанция от персонажа, FULL 100 / hide 200 / hysteresis 10 studs по умолчанию; индивидуальные профили M633 сохраняются. FULL pin для текущей дистанции оружия (с запасом), атакующего игрока существа, смерти ранее видимого FULL и GP-тестовых существ. Если серверный FULL ещё готовится, LOD1 держит видимый placeholder до readiness (spawn reveal и explicit opt-out сохраняют прежнее поведение).
- `MnpcLodRegistry` генерируется Host Agent из актуального реестра, с revision/identity/alignment guards; отсутствие записи, stale/unverified или отказ загрузки приводит к dummy. Регистр обновляется при старте Host Agent и соответствующих authoring mutations; текущая игровая сессия использует снимок модуля при require, изменения применяются при следующем запуске/публикации. Сохранённый explicit OFF не мигрирует в ON. Новые/default без сохранённого профиля включены.
- Локальные заменители привязаны WeldConstraint к navigation root, не являются серверными коллайдерами и не участвуют в бою. UNLOADED удаляет локальный заменитель. FULL восстанавливает локальную видимость. Streaming removal/return и teardown очищают локальные части, маски и подписки. Общая маска с NPC weapon visibility не перетирает отдельное состояние оружия. Локальные visual effects скрываются; как и M625, запись server false поверх уже false неразличима без отдельного состояния.
- Оба client attack composers используют общий `MnpcRigObserver` и отключают собственные sampler bindings вне FULL; при возврате подписываются на текущий риг. Overhead UI не показывается вне FULL (pool не реализуется этим этапом).
- Один существующий world Heartbeat, отдельная ограниченная полоса MNPC (до 4 переходов и 16 проверок очереди за кадр), сортировка только pending transitions по расстоянию; observation 0,25 с по реплицированным MNPC, немедленная переоценка при смене root / смещении ≥64 studs. Не общий static index и не общий operation budget с окружением. Бounded async requests переиспользуют HouseMeshRequests, один prototype на тип; до 4 слотов, retry 15 s. Нативный mesh/texture download и CPU budget не гарантируются.

## Что НЕ считается завершённым

**Визуальный LOD не равен полной изоляции native skeleton.** M638 маскирует реплицированный FULL, не уничтожает его локально и не подменяет серверную боевую позу. Если серверный Animator остаётся реплицированным, он может вычислять анимацию даже при LOD1/UNLOADED; M627 это подтвердил. Нативный zero-Animator критерий A07, production initial shell-only, production demand admission/release остаются открытыми. M632 остаётся Studio pilot default OFF; включать его в production без проверки восстановления боевой позы и admission после телепортации нельзя. Пользователь не обязан готовить реальные LOD1 для проверки следующих шагов. Не объявлять выигрыш CPU/FPS/памяти без измерений.

## Проверки

Lua oracle исполняет текущие Policy, LocalVisibility и Controller на doubles: обе категории, границы hysteresis, dummy → mesh, FULL → LOD1 → UNLOADED, shell/reacquire, cleanup, композиция двух владельцев видимости. Python проверяет projection, stale/invalid identity, no-LOD registry и reuse. Native Studio/DEV, двухклиентская репликация и физический телефон NOT_RUN. Обычный Play: при дефолтных дистанциях у игрока FULL, после выхода за 110 studs красный блок, после 210 studs нет локального визуала; на обратном пути 190/90 studs. Атакующая игрока цель / дальность оружия могут принудительно сохранить FULL. Проверка не требует публикации LOD1.

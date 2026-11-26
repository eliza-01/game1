# M532 · Headshot и GP Recovery

## Контракт

- MeleeTargetQuery.Find остаётся единственным источником целей урона. Один RaycastAimRegions на непустой checkpoint, 32 studs от точки reticle ray, ближайшей к атакующему. Только выбранная голова уже попавшей в сектор цели; препятствия проверяются от корпуса игрока как раньше. Не менять bow, радиусы, урон, коэффициенты.
- GP Export (`guideExport`) сохраняет сессию и выводит завершённые результаты, даже во время боя. Done закрывает только завершённую серию. GP_TRIAL печатается немедленно. Retry (`guideRetry`) прерывает активное испытание или удаляет последний результат и печатает GP_TRIAL_RETRY; Next повторяет. Повторный Retry до запуска Next не удаляет другие результаты. Skip (`guideSkip`) помечает текущее/следующее испытание `manual_skip`, не включает его в средние. Cancel остаётся явной отменой. Экспорт доступен владельцу GP только в Studio, через существующий RemoteFunction. Не сохраняем данные между Play сессиями; Output можно скопировать до Stop.
- Временный `gp_melee_timing_only` только для Studio GP, когда клиент не нашёл melee descriptor/таймлайн с HitEnd. Сервер независимо строит cadence из AttackSpeed, HitEnd 80% цикла, для dualswords HitFirst 40%; обычный HitEnd/Arc, cooldown, stun, weapon identity, environment bounce и DamageService не обходятся. Без анимации визуальный удар отсутствует; это тестовый режим, не production fallback. Отдельная группа `/timing-only` и счётчик fallbackAttacks. Dualswords с клипом 1hs маркируются `/animation-preview`. Bow требует authored Release.
- `firstCenterInRangeSeconds` — приближение по центрам в горизонтальной плоскости, не контакт хитбоксов. `firstHitSeconds` — первое фактическое снятие HP. RunSpeed исходный stat + studs/s. Межударная задержка ещё не локализована; не меняем cadence и баланс.

## Приёмка Studio

1. Rojo Sync, новый Play. GP → Enter test → Guided → Next. На первом бою Export, проверить PARTIAL и отсутствие сброса. Завершить, убедиться в GP_TRIAL. Retry → Next, Skip → Next, сверить индексы, отчёт исключает skipped. Done закрывает только после всех испытаний.
2. На bigsword без 2hs клипа убедиться в damage, обычном AS и gp_melee_timing_only в отчёте. При наличии авторского клипа используется он. Не использовать timing-only для окончательного баланса анимаций.
3. Кинжалом на 3 studs навести на голову: обычный валидный удар получает ×1.5; наведённая голова вне сектора не получает урон. Навести на корпус — обычный удар. Две цели, голова одной — только она получает headshot. Стена блокирует, bow без изменений.
4. Проверить timeout, смерть, повтор и отсутствие наград. Продолжить оставшиеся этапы; для сравнения заново пройти меч/кинжал после изменения Headshot.

Команда Client Command Bar в Play: `print(game.ReplicatedStorage.Game1Remotes.GameplayTest:InvokeServer("guideExport",{}).message)`.

## Откат

Обратный git apply M532 на остановленном Play. Ассеты, Database gameplay, SQLite и опубликованные ID не меняются. Studio-приёмка не выполнена.

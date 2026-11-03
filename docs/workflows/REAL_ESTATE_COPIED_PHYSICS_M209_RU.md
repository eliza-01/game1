# M209 — Real Estate: CollisionFidelity после копирования в Workspace

## Симптом и границы

В существующем Sync `StudioRealEstateCollisionPolicy.Apply` выставляет
`PreciseConvexDecomposition` для каждого `MeshPart` с `CanCollide=true`.
При ручном копировании подготовленного дома из `ServerStorage` в `Workspace`
процедура Sync **не выполняется**, поэтому копия может остаться с
`CollisionFidelity=Default`. Повторный Sync исправляет это, но не должен быть
обязательным шагом после размещения. Точное поведение Roblox clipboard/Clone
подлежит проверке в Studio; код не утверждает, что каждый Clone сбрасывает свойство.

## Изменения

- `StudioRealEstateCollisionPolicy` после Sync сохраняет применённые настройки
  коллизии в трёх атрибутах каждого MeshPart. Атрибуты — снимок действующей
  настройки, **не второй источник данных** и не новая таблица.
- `StudioRealEstatePlacedPhysicsGuard` слушает **только добавление моделей**
  с `Game1RealEstateSlug` в Workspace в Studio Edit Mode. После завершения
  копирования сверяет физику всех MeshPart с сохранёнными настройками.
  Любая включённая коллизия гарантированно получает `PreciseConvexDecomposition`.
- Для старых шаблонов без новых атрибутов используются фактические значения
  `CanCollide` и `DoubleSided` самой копии; повторная публикация не требуется.
- При запуске плагина выполняется однократная проверка уже размещённых моделей;
  бесконечного мониторинга/покадровых обходов нет. В Play Guard ничего не меняет.
- После размещения копия теряет ошибочный атрибут `Game1RealEstateTemplate`.
  Существующие системы размещения, pivots и анимаций не меняются.

## Ручная проверка в Studio

1. Установить плагин, переоткрыть Studio. Полный Sync дома желателен для записи
   явных атрибутов на шаблон, но старый шаблон тоже поддержан.
2. В `ServerStorage.real_estate.<slug>` у `col_mesh` проверить `CanCollide=true`,
   `CollisionFidelity=PreciseConvexDecomposition`.
3. **Скопировать** (не перемещать) дом в Workspace через Studio Explorer.
   Подождать завершения вставки. У копии проверить те же два свойства;
   `CollisionFidelity` должна стать Precise без нового Sync.
4. Повторить для `door`, `window_frames_glass`, а также визуала с `CanCollide=false`.
5. Перейти в Play: Guard не должен вмешиваться в игровую физику.

Если проблема воспроизводится, сравнить свойства исходного `col_mesh` в
ServerStorage и вставленного MeshPart в Workspace **до/после 0.1 с**;
так можно отличить некорректный шаблон от поведения Studio Clone/clipboard.

## Миграция и ограничения

SQLite/JSON/publication IDs не изменяются. Ни один Model Asset не публикуется
повторно. Это только Studio-plugin authoring correction. Studio runtime и
копирование пользовательской конкретной модели не были выполнены в Python-среде.

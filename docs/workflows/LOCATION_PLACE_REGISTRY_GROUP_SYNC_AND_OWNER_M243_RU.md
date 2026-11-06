# M243 · Place Registry Sync group / Location Find–Sync owner

## Сценарии

- `Place Registry → Scan Place → Sync group (N)` расположена рядом с `Repair group (N)`.
  Она использует **существующий** `phase=sync`: только `canSync` и реально устаревшие размещения
  выбранного slug. Другие группы, неопознанные и неоднозначные объекты не затрагиваются.
- Подтверждение бэкапа, обычный confirmation, запись операции в журнал и Undo остаются
  обязательными. После успеха выполняется автоматический Scan с сохранением UI.
- При отсутствии подходящих размещений кнопка группы неактивна. Глобальная Sync All сохранена.

## Исправление DecoManager Find → Sync

В M239 сканер выбирал **ближайшую** модель с `Game1DecoAssetSlug` и `Game1DecoInstanceId`,
а `DecoPlacedAssetSync.targets()` отбрасывал все вложенные модели, имеющие над собой
другую модель с атрибутом slug. Поэтому корректно найденный MeshPart мог получить
`scanned Location instance no longer exists; rescan`, хотя объект не удалялся.

M243 вводит узкий `StudioLocationPlacementOwner.ForPart`: **один** алгоритм
определения владельца и для Find, и для Sync. Ближайший маркированный контейнер
либо является валидным владельцем указанного slug, либо прерывает поиск;
нельзя проходить сквозь чужую/повреждённую маркировку до вышестоящей группы.
Это поддерживает вложенные вручную группированные размещения, но не создаёт
автоматических привязок по имени или одному историческому Mesh ID.

При Sync дополнительно проверяется владелец каждой отмеченной строки.
Если у обновляемого корня есть отдельно маркированные вложенные размещения,
**геометрический** Sync отклоняется до `RigSwap.Prepare`: нельзя уничтожить
самостоятельную дочернюю декорацию при замене родительского rig.

Не меняются опубликованные ID, Asset Registry, положение объектов, скелеты,
коллайдеры и логика `StudioManagedRigSwap`. Работа с Place только по явному Sync.

## Граница Real Estate

Модули `StudioRealEstate*`, API и UI Real Estate не изменены; система не использует
Location-специфический ownership resolver. Общий `StudioManagedRigSwap` также не изменён.

## Проверка

`python system/verify/verify.py`, `python system/studio-plugin/validate_luau.py`,
`node --check system/control-center/static/place-registry.js`,
`python -m unittest discover -s system/verify -p 'test_location*.py' -q`,
`python -m unittest -q test_location_place_registry_m243` (из `system/verify`).
Старые Real Estate тесты требуют сравнения с базой M242: набор тестов содержит
устаревшие ожидания и не является подтверждением корректности в живой Studio.

**Не проверено:** реальный Find → Sync вложенной декорации и Real Estate
Edit/Sync в Roblox Studio. Испытывать на резервной копии Place, наблюдать
CFrame/Size и Undo до массовых операций.

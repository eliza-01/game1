# M162 — legacy shared atlas inheritance / Studio Sync

> **Исторический отчёт по патчу.** Фиксирует состояние после M162 на 29–30.10.2026. Действующие требования: [ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).

## Проблема

После переназначения общего атласа `structures_01_2048x2048_atlas.jpg` Stone Fence 01 показывал `PUBLISHED`, а зависимые Stone Fence Pillar 01, Wooden Fence 01, Wooden Fence Pillar 01 и Stone Ladder 01 — ложный `UPDATE_AVAILABLE`. Реальный Image Asset ID принадлежит варианту в Atlas Registry (`119920676388867` в диагностическом примере); legacy `texture_reference_slug` у зависимых consumers читался как старое поле публикации владельца, хотя registry уже был актуален.

## Решение и контракт

- Resolver для legacy-reference обязан получать publication state из current Atlas Registry через владельца, а не из пустых legacy-полей.
- Все consumers одного варианта используют один Image ID; ни один не делает повторную публикацию для наследования.
- Personal Studio Sync и общий sync не отмечают редакторскую ревизию подтверждённой до реального подтверждения от Bridge; после sync UI перечитывает статусы.
- Сохранение зависимого ассета не должно неявно превращать legacy-reference в самостоятельный binding.
- Модели/текстуры/ID/FBX не переписываются в рамках исправления статусов.

## Проверки в момент этапа

Отчёт о M162 фиксировал 568 Python-тестов, `verify.py`, Luau и JavaScript syntax checks; на копии реальной SQLite базы пять потребителей получили PUBLISHED. Реальное состояние конкретной открытой Roblox Studio **отдельно** не установлено тестами. В текущем срезе присутствует регрессионный `system/verify/test_location_asset_legacy_atlas_inheritance_m162.py`.

# M652 · Hitbox Cache Compatibility

**M652 · Hitbox Cache Compatibility (KBN-0039-T02/T03): CODE_COMPLETE, native coverage open.** Свежий дамп `game1_diag_2026-11-28_17-27-55.zip` содержит 4 реальных v2 captures; лог Studio M651: 31 mesh read (14 guard, 5 gremlin, 1 warsmith, 11 Character), 3 asset mismatch, попадания/headshot/death подтверждены владельцем и логом. Один владелец compact session/asset definitions, session key не зависит от world AABB RootCollider; структура, MeshId, scale и bone mapping строго совпадают, frame tolerance 2 единицы v2 quantization (0.0002), root center меняет только консервативный broad radius. Неоднозначные/несовместимые записи отклоняются с причиной. Registry v2 и 4 записи не изменены. Native parity NOT_RUN; Runtime oracle сохранён, Character capture и полное coverage остаются следующей задачей, не удалять fallback до приёмки. См. `docs/workflows/M652_HITBOX_CACHE_COMPATIBILITY_RU.md`.

## Контракт

- M651 хранит v2 mesh-relative signature, а прежний session key содержал размеры AABB, меняющиеся при yaw. M652 переносит единственный session cache в HitboxAssetDefinitions (до 256 записей, без вершин). Builder остаётся чистым oracle. Registry v2 не переписывается.
- Сравнение структурное; допускаются 2 квантованных единицы только в spatial frames, scale и identity строго совпадают. При неоднозначности отказ. Коррекция broad sphere по смещению центра + 0.005 запаса на округление не меняет сохранённые local boxes, но эквивалентность на границах Headshot требует native проверки.
- После yielding mesh read повторная проверка актуальной позы до синхронного oracle. Никаких новых loops/remotes, изменения damage, SAT, AI, физики или LOD.
- Лог asset definition accepted один раз на ключ; при отказе конкретная причина (mesh frame/bone pose/mapping/root up и др.). Не обещать, что все захваченные записи будут приняты: фактические runtime frames отсутствуют в логе M651.
- Lua double: 360 yaw/translation, смена root size, tolerance, duplicate, pose/mesh/scale invalidation, vertex lease. Python fixtures независимы от реального непустого registry. Studio/DEV parity и Character capture NOT_RUN.

## Приёмка

Запустить Studio Play без повторного capture, проверить попадания и прислать начальные строки `[hitbox-assets]` и `[combat-hitbox]`. Если сохранённые captures не совпадают, конкретную причину исследовать до миграции Character. DataStore unavailable в unpublished Studio ожидаем; asset 203785492 ранее отмечен в M132 и не найден в исходниках, не менять наугад.

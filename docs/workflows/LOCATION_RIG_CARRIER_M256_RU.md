# M256 · Location Assets: authored `rig_carrier` v2 (каноническая публикация; структурный Repair запрещён)

## Статус и границы поставки

Переход на v2 затрагивает **только** зарегистрированные Location Assets. Character, NPC, Monster, Real Estate и runtime домов остаются отдельными доменами. `rig_carrier` — реальный MeshPart из **Blender FBX**, не искусственный Part и не копия визуального меша. Единственным владельцем Bone-иерархии служит carrier. Atlas, Alpha, Material и COL не должны применяться к нему как к visual.

**Эта поставка НЕ является завершением массовой миграции.** Диагностический архив от 07.11.2026 содержит записи 29 Location Assets, но не содержит исходных FBX и `.rbxl`: ни одна публикация не содержит проверенного v2 manifest. В данном окружении нельзя выполнить Blender round-trip этих исходников, Open Cloud-публикацию, Place Repair, Studio Save/Reopen или Play-регрессию. Любое сообщение об обратном было бы неверным. Обязательна последующая работа на локальном проекте и в Roblox Studio с резервной копией.

## Архитектура и владение

| Компонент | Ответственность |
|---|---|
| `location_rig_contract.py` | Детеминированный, без Blender/Roblox, schema v2: роли, уникальные имена, кости, хеши |
| `location_rig_authoring_fbx.py` | Явная конвертация SOURCE FBX → НОВЫЙ FBX с настоящей минимальной carrier-геометрией, без перезаписи исходника |
| `prepare_model_publication_fbx.py` | Fail-closed pre/post Blender round-trip; для Location (`geometry_only`) — обязательный v2 manifest, без скрытого создания carrier |
| `LocationAssetStore` | Атомарная запись v2 manifest по immutable Model ID вместе с записью публикации; backup SQLite перед миграцией схемы |
| `StudioLocationRigCarrier.luau` | Отдельная проверка опубликованной геометрии и read-only диагностика размещений |
| `StudioLocationRigCarrier.luau` | Проверка опубликованной структуры и диагностика legacy RootPart; не ремонтирует скелет на Place |
| `StudioPlaceRegistryInventory/Repair` | Only registered Location Asset allowlist, версии, причины блокировки, явный Repair через `ChangeHistoryService` |
| `DecoAssetLoader`, `StudioPlaceRegistrySync` | Загрузка проверенной v2 модели и независимый Sync ресурсов; топология не чинится внутри Sync |

Версионированный manifest содержит `schemaVersion=2`, `parts[]` с `name`, `role` и количеством вершин, `bones[]` с `parent` и rest-матрицей, `structuralHash`, `inventoryHash`, `boneHash` и SHA источника. **В нём ещё нет подтверждённых Roblox Mesh ID/позы импортированного FBX** — их можно фиксировать только после действительной Studio-проверки каждой публикации; присваивать фиктивные ID запрещено.

Роли: `visual`, `collider` (имена `col_mesh` / `col_*`) и `rig_carrier` **только у скелетных моделей**. Если FBX не содержит Bone, это **Static**: `rigKind=static`, `bones=[]`, `carrierName=null`, `rig_carrier` не требуется и запрещён. Если есть Bone — **Skinned**: `rigKind=skinned`, ровно один настоящий FBX-authored `rig_carrier`, кости только под ним. Ни один из типов не допускает `RootPart` или импортные `Motor6D`. Оба типа должны содержать хотя бы один visual MeshPart. Обычные кусты/камни не должны подвергаться конвертации или перепубликации ради carrier.

## Сборка одного авторского FBX

При наличии реального файла на локальном ПК:

```powershell
blender -b -t 1 --python system/asset-manager/location_rig_authoring_fbx.py -- `
  "E:\path\original.fbx" "E:\path\carrier_v2.fbx" "E:\path\carrier_v2.manifest.json"
```

Source оригинал сохранится. Blender экспортирует отдельный FBX и повторно импортирует его, проверяя структуру. Затем **проверить скелет и skinning в Roblox Studio**, выбрать этот FBX в Location Asset Model editor и явно опубликовать новый Model ID. Model ID сохраняется по существующему immutable publication history; атлас не републикуется и не меняется. Если Blender изменил bind pose, потерял кости, или importer добавил `RootPart`/`Motor6D`, публикация и размещение должны остановиться — не обходить валидацию.

## Read-only каталог до миграции

```powershell
python system/asset-manager/audit_location_rig_migration.py `
  E:\RobloxProjects\game1 E:\RobloxProjects\game1\location_rig_migration_report.json
```

Сканирует **все** зарегистрированные Location Assets, включая те, для которых FBX отсутствуют. Не изменяет БД, Place, историю или исходники. Повторить после загрузки источников и после публикаций.

## RootPart: только новая публикация FBX

`Импортный RootPart — требуется перепубликация FBX` означает, что текущей
канонической FBX-публикации ещё нет. Когда новый Model ID уже имеет v2 manifest,
то же старое размещение помечается как требующее **обновления из публикации**,
а не очередной перепубликации. Такой экземпляр нельзя исправлять через Repair. **Repair не переносит Bone, не
создаёт carrier и не удаляет RootPart.** Перепубликуйте исправленный исходный
FBX через Location Assets → Model · FBX → Publish. Open Cloud выдаст новый
**Model ID**; история прежних Model/Mesh ID сохраняется, Atlas/Image ID не меняется.

Новый исходник должен содержать настоящий `rig_carrier`, полный набор visuals,
COL и Bone tree. Blender round-trip и Studio Import обязаны проверить его.
Если публикация прошла проверку, новые размещения получают всю опубликованную
структуру без самодельного Repair. Старые размещения сохраняются как legacy и
не изменяются при Scan/Repair; их обновление требует отдельного подтверждённого
Sync с полной заменой rig из опубликованного Model ID. **До Studio-регрессии
не использовать массовое обновление**.

Repair остаётся только для метаданных/Placement ID уже канонических моделей.
Любой неканонический риг показывает требование публикации вместо кнопки Repair.


## Безопасная последовательность полной миграции

1. Сохранить `.rbxl` через Studio Save to File и отдельные копии `.control-center/game1.db`, реестров, FBX и исходных Blender-проектов; записать revision и old Model IDs.
2. Запустить read-only audit всех slug и всех размещённых объектов; записать исходную иерархию/свойства. Не пропускать исторические модели, даже если текущий Model ID уже изменился.
3. По проверенному FBX-анализу разделить Static (без Bone и carrier) и Skinned (есть Bone). Только для Skinned с отсутствующим carrier подготовить новую authored FBX-версию. Статические ассеты оставлять как есть; при новой публикации записывать v2 Static manifest.
4. Переопубликовывать только FBX с изменённой геометрией или скелетной структурой. Статические Model ID с прежним SHA и без костей не переиздавать ради carrier. Не трогать atlas bindings и историю Model/Mesh IDs.
5. Для каждого структурного типа проверить **новое размещение** из канонической публикации на копии Place: `lantern_01__9304a338`, multipart/skinned/static, с COL и без COL. Старые экземпляры с RootPart не исправлять через Repair.
6. Сравнить pivot, Bone rest/posed, Mesh ID, Size, CFrame, коллизию, Alpha и SurfaceAppearance у новой публикации. Проверить Save/Reopen и Play; для Location Assets не требуется анимационный тест.
7. Старые экземпляры до отдельной проверенной операции полной замены rig оставлять в статусе legacy. После подтверждения замены из опубликованной модели сравнить трансформации, Undo и сохранение Place; не использовать массовый Sync заранее.
8. Повторный Scan, ревизия Place, сохранение `.rbxl`, итоговый отчёт. Для отката использовать последнее Undo либо резервный `.rbxl` с SQLite; никаких скрытых повторных Repair.

## Реальные критерии готовности

Полный переход Skinned-ассетов готов **только** после их переэкспорта/переопубликования, подтверждения настоящих carrier Mesh IDs и Bone bind-poses в Studio, миграции затронутых placements или документированных блокеров, проверки `lantern_01__9304a338` и multipart-кейса, Save/Reopen, Play, Undo, полного набора тестов. Статический `verify.py` не является заменой Studio-регрессии.

## M258 · Publish and Apply: authoring перед публикацией

Если зарегистрирован старый **скелетный** FBX с Bone, но без `rig_carrier`, кнопки `Publish and Apply` и
`Publish ready` запускают **отдельную, явно обозначенную стадию Blender
authoring**. Её результат — новая неизменяемая версия FBX в
`assets/authoring/location-assets/<slug>/`, со связанным manifest. Исходный
`assets/source/.../<slug>.fbx` предварительно архивируется стандартным
`LocationAssetStore.register`; текущий Model ID и Atlas/Image ID сохраняются до
успешного Open Cloud upload. Затем вызывается прежняя строгая проверка
`prepare_model_publication_fbx.py` и публикуется **новый** Model ID.

Этот переход **не** подставляет carrier в staging FBX, не создаёт MeshPart в
Studio и не исполняет структурный Repair. Любое расхождение bind/rest,
неподдерживаемая структура RootPart или проблема с Blender — блокирующая
ошибка **до публикации**, с прежним Model ID. Studio Import всё равно обязан
подтвердить фактическую структуру опубликованного рига.

`rig_carrier` исключён из редактируемой физики и не считается visual/COL.

**M259 · исправление условия применимости.** Наличие костей (а не факт регистрации Location Asset) определяет потребность в carrier. Статический FBX публикуется без скелета, без RootPart и без carrier; pre/post staging создаёт v2 manifest с `rigKind=static`. Для уже опубликованного статического FBX допускается проверяемый legacy-режим без v2 manifest: модель и исходник должны иметь совпадающий SHA, FBX-анализ — ноль Bones/непривязанных armature, а Studio — ноль Bones, RootPart, carrier и importer Motor6D. Такая модель не требует перепубликации только ради метаданных. Если хотя бы одно из доказательств отсутствует, fail closed. Atlas не меняется.

Blender-генератор `location_rig_authoring_fbx.py` работает только с настоящим существующим скелетом. Он больше не создаёт фальшивые armature и root bone для статических ассетов.
Конверсия не применяется к Character, Real Estate, Monster, NPC или Weapon.

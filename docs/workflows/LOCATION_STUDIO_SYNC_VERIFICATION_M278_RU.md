# M278 · Location Asset Studio Sync — подтверждение вместо догадки

## Контракт статусов

- `AtlasRegistry.binding().syncStatus` — состояние подтверждения **привязки атласа**, а не сравнение Workspace с публикацией. Для Real Estate его семантика не меняется.
- `LocationAsset.studioSyncStatus = unverified` — опубликованные ID имеются, но подтверждения актуальности в текущей Studio пока нет. Это **не** требование Sync.
- `Studio Find -> verification = current` — проверены Model/Mesh IDs, Texture/ColorMap, Alpha и канонический rig в пределах имеющегося Place; непривязанных кандидатов нет. Можно подтвердить atlas binding revision, **не изменяя Workspace**. Ноль размещений также означает отсутствие необходимых операций Replace. Неполные отчёты старых Studio-плагинов не дают права на подтверждение.
- `Studio Find -> verification = pending` — подтверждены конкретные изменяемые managed MeshParts. Замена по-прежнему только после явного выбора и согласия пользователя.
- `Studio Find -> verification = review_required` — есть непривязанные/непроверенные/неканонические части либо отчёт не доказывает актуальность. Автоматического подтверждения нет.

Библиотека отображает `Studio Sync pending` только после Find для конкретного набора (Model Asset ID, Atlas ID, binding revision, authoring revision, Alpha). Результат хранится **только в UI-сессии**; после перезагрузки он не считается свежим. Мануальные изменения Place после Find требуют нового Find.

## Границы безопасности

1. Find остаётся строго read-only **относительно Studio Place**. На Host Agent допускаются запись scan-инвентаря и подтверждение revision в SQLite, если отчёт доказывает актуальность.
2. Нет автоматического Replace и никакого изменения MeshPart, Weld, Bone, Attachment, Pivot, CFrame, размеров, материалов или физики.
3. `mark_synced` выполняется только при совпадении Model ID, Model SHA, Atlas ID, atlas revision, authoring revision и Alpha с исходным снимком. Атомарная проверка atlas revision в Atlas Registry остаётся в силе.
4. History Scan, Replace, history/audit сохранены без изменения механизмов и протокола Studio-плагина.
5. Перепубликация ресурсов, уже подтверждённые Image/Model Asset ID и записи Place Registry не меняются.

## Проверка

После установки M278 открой `ivy_02`, `ivy_05`, `bush_02` и выполни `Sync Studio → Find Mesh IDs`. Если все копии текущие или копий нет, появится подтверждение без Replace. Если Studio реально обнаружит старые MeshPart/атлас, список покажет их, и только явный Sync сможет изменить Place.

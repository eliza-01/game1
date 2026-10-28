# M152 — Real Estate: Workspace sync that includes manually placed template clones

## Причина
В M140/M143 точечный и полный Studio Sync считали `Game1RealEstateTemplate=true`
признаком «не размещённого» дома. При ручном Clone из ServerStorage этот
атрибут оставался на экземпляре в Workspace. Оба синхронизатора игнорировали
такой дом, хотя `Game1RealEstateSlug` корректно присутствовал. Результат
`placed houses 0/0` ошибочно подсвечивался как успешный.

## Контракт
- Только `ServerStorage` является местом канонического template. В Workspace
  модель с совпадающим `Game1RealEstateSlug` считается размещённой независимо
  от папки и от случайно скопированного флага template.
- Один целевой список по событию Studio Sync для точечного, полного,
  коллизионного и текстурного обновления. Вложенные модели с тем же slug не
  учитываются повторно.
- Успешно обновлённому объекту снимается флаг template и фиксируется
  новый `Game1RigAssetIds` / актуальный ID модели. `DoorAssembly` сохраняет
  текущий pivot. Не меняются кости, Blender armature, мебель и размещение.
- Никакого изменения источников FBX, SQLite и опубликованных Asset IDs.
- Обе операции отдают `placedSyncVersion=2`, количество найденных/обновлённых
  домов, предупреждения и, при полном Sync, отдельные счётчики коллизий.
- `0/0`, неполное обновление и устаревший Studio Bridge не являются зелёным
  подтверждением успеха в Asset Manager.

## Установка и проверка
Закрыть Studio; остановить Control Center; применить patch, запустить тесты;
затем `system/studio-plugin/install.ps1` и `system/studio-plugin/audit.py`.
Запустить Control Center и Roblox Studio заново. После публикации новой двери
повторить **Sync model · template + placed**, затем проверить новый
`Game1DoorModelAssetId` на соответствующих экземплярах Workspace.

Реальную замену внутри Roblox Studio нужно подтвердить вручную: статические
тесты не эмулируют Engine `Model:PivotTo` и `AssetService:LoadAssetAsync`.

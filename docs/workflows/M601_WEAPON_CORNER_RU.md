# M601 · Weapon corner / Newbie Slayer

- Mobile slots: DeviceSafeInsets, ClipToDeviceSafeArea, 2 px сверху и справа. Размер вычисляется из CoreUISafeInsets для совпадения с Attack. Остальные ScreenGui не меняются.
- Database: `newbie_slayer_01` (Model 72367246036941) → `weapon_003`, существующая запись bigsword LVL 1. Публикация модели сама по себе не создаёт binding. JSON и Luau registry согласованы. Никаких fallback-характеристик.
- Если категория пуста, клиент пишет причину и сбрасывает кэш каталога; следующий тап повторяет загрузку. Серверная авторизация неизменна.

## Studio / DEV acceptance

1. Rojo Sync. Проверить Database → Model bindings. Убедиться, что в ServerStorage есть `weapons.bigsword.newbie_slayer_01.model.newbie_slayer_01` (Sync Model при отсутствии).
2. Выбрать bigsword на PC и touch. Проверить атрибут EquippedWeaponSlug и реальную модель. Сменить на sword и обратно.
3. В эмуляторе и на телефоне проверить верх/право: 2 px от device safe area, сохранение размера при смене ориентации, отсутствие пересечения Roblox UI и debug.
4. Для опубликованного DEV пересобрать Runtime и опубликовать. Фактическая проверка модели, анимаций и touch в Studio/DEV остаётся открытой.

## M603 · Исправление Rect

В Studio M602 обнаружено падение `MobileWeaponSlots.Layout`: у Rect из `GuiService:GetInsetArea` нет свойства Size. Размер вычисляется как `area.Max - area.Min`. Геометрия, DeviceSafeInsets и отступ 2 px сохранены. Приёмка: touch Play без ошибки Rect; четыре кнопки в углу, переключение типов.

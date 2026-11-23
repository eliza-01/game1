# M449 · Options → Sockets · постоянные USE / AIM радиусы

## Назначение

В рантайме игровые зоны берутся из **одного** сохранённого профиля Options, а не из временных значений HS Studio Debug. Профиль относится к типу сокета, не к отдельному дому/костру и не к устройству ввода. Все размещённые экземпляры одного сокета получают одинаковые настройки.

## Владение и генерация

- `system/control-center/options_store.py`: whitelist допустимых `house`/`campfire` сокетов; при сохранении проверяет числовые поля, конечность значений, диапазоны **USE 2–30 studs**, **AIM 1–16 studs**, а также AIM ≤ USE; запрещает неизвестные имена, пустые поля и AIM для сокетов без AIM.
- `assets/manifests/options.json` (`socketRanges`): единственный постоянный источник. Обновление частичной группы не стирает другую группу и прочие Options. При первой миграции `fire_socket` наследует прежние сохранённые `CampfireInteractionRadius` и `CampfireAimRadius` из `config/mechanics/fireplace.json`, если они существуют.
- `src/shared/GameOptionsRegistry.luau`: генерируется `OptionsStore` из валидированного JSON. В репозитории не нужно вручную редактировать этот файл для настройки радиусов. Контракты `HouseSocketContract` и `CampfireSocketContract` читают `socketRanges` при загрузке; прежние значения остаются fallback для старых снимков без этого поля.
- `HouseSocketService`, `LocationCampfireService`: сервер авторитетно проверяет USE. `HouseSocketPromptController` и `HouseFireplaceController` используют те же контрактные USE/AIM для отображения и проверки наведения. Промежуточные данные клиента не расширяют серверную дистанцию.

## Редактор

**Control Center → Options → Sockets · USE / AIM**: отдельно House (двери, замки, сундук, лифты, камин) и Campfire (`fire_socket`). Неинтерактивные `chimney_01_socket`, floor spawn, `cooking_pot_01_socket` и внутренний `cooking_pot_socket` не создают игровых зон и в редактор не включены. Для дверей/замков AIM не создаётся автоматически: оставлен существующий prompt flow. Единицы — studs.

**Studio Play → HS**: кнопки `+ / −` работают как временные per-player overrides (Studio-only Player Attributes). Изменение HS **не сохраняется** и не меняет FBX, настройки проекта или текущий опубликованный Place. Для постоянной настройки значения нужно ввести в Options и нажать **Save Socket Ranges**, затем синхронизировать Rojo и начать новый Play. Никакой автоматической записи из Studio Debug нет.

## Проверка в Play

1. В Options изменить USE/AIM у `fireplace_01_socket` и `fire_socket`, сохранить, синхронизировать Rojo и начать новый Play.
2. В HS включить зоны и подтвердить начальные радиусы и на доме, и на костре.
3. На расстоянии за USE/в USE и вне AIM/в AIM подтвердить появление E/F и общей информационной панели, с учётом окклюзии.
4. В HS изменить радиус временно. Перезапустить Play: должно вернуться сохранённое значение Options.
5. Убедиться, что `cooking_pot_01_socket` отображается только как HEAD-маркер, не как отдельная интерактивная зона.

Это исходниковая проверка контракта. Фактический Studio Play и опубликованный Runtime Place должны проверяться отдельно.

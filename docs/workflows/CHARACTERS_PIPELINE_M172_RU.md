# M172 — Characters: понятный pipeline публикации и настройки

**База:** `game1_diag_2026-10-30_18-38-46.zip`. Этап UI-first перед R3, только Characters.

## Элементы интерфейса

- **Save Identity** — только если изменены ID, race, gender, display name. Это **отдельная рискованная миграция путей** исходного character и анимационного профиля. Сохраняет присвоенный Model Asset ID; требует подтверждения. Не относится к модели или стартовой статистике.
- **Reset** — восстанавливает сохранённые значения *текущего выбранного архетипа*. Не удаляет регистрацию и не переключает на New. Оранжевая обводка.
- **Save Starting Stats** — активна/зелёная только при изменениях. Сохраняет в `character_stats` в SQLite, затем вызывает экспорт `assets/manifests/character-archetypes.json` и `src/shared/character/CharacterRegistry.luau`. Диалог перечисляет `было → стало` по каждому изменённому полю. **НЕ** выполняет повторную публикацию модели или загрузку Model Asset в Studio. Rojo переносит сгенерированный ModuleScript; без подтверждения работы Rojo UI честно отображает `pending`, новую игру Play надо перезапустить для новых стартовых значений.
- **Reg + Publish** — одна UI-операция вместо Choose FBX, Publish Model, Sync Studio. Для нового персонажа выбирает FBX, регистрирует модель и скелет, публикует новый immutable Roblox Model Asset ID и загружает в Studio через Bridge с валидацией rig. Для уже опубликованного без ожидающей ревизии предлагает выбрать replacement FBX. Для локально зарегистрированного/CHANGED и pending replacement допускает продолжение прежней ревизии. Результат включает статусы стадий `validate/register/publish/studio` и новые/предыдущие ID.
- **Set as Startup** — устанавливает `activeArchetypeId`; выбирает стартовую модель для runtime, если нет явного override. Не означает публикацию или смену игрового персонажа в уже запущенной сессии.

Длинные пояснения находятся в tooltip `?` рядом с действиями, поддерживаются мышь и клавиатурный focus. Текст отчёта не вставляется через `innerHTML`.

## Граница атомарности

**Невозможно выполнить одну ACID-транзакцию сразу через SQLite, Roblox Open Cloud и работающую Roblox Studio.** Это не обещается пользователю: единый серверный route orchestrates последовательные checkpoints, сохраняет текущий Roblox Asset ID до успеха публикации, а при ошибке возвращает *частичный* итог. Если новый ID уже получен, а Studio Bridge недоступен, **не откатывать публикацию**, не повторять upload: UI предлагает `Retry Studio Sync` конкретного ID.

Если Open Cloud отказывает после регистрации, canonical FBX и локальная ревизия могут быть уже сохранены: это явно отмечается в отчёте, повторный вызов продолжает с зарегистрированной ревизии. Строгое двухфазное хранилище со staged/commit FBX требует отдельного этапа R3 с проверкой SQLite, source backup и crash recovery; его **не** следует имитировать UI-кнопкой.

Ранее существовавшие REST endpoints `/api/characters`, `/:id/identity`, `/:id/stats`, `/:id/replace-model`, `/:id/publish`, `/:id/sync`, `/:id/activate` сохранены для совместимости. Новый `POST /api/characters/workflow` предоставляет последовательный отчёт, не изменяя контракт других категорий.

## Приёмка Windows + Studio

1. Открыть Characters: не видеть отдельные Choose FBX / Publish Model / Sync Studio; видеть `Reg + Publish` и подсказку `?`.
2. У выбранного персонажа изменить HP, проверить зелёную Save Starting Stats, затем Reset и неизменность сохранённых значений. Снова изменить HP и сохранить: диалог показывает старое и новое значение + экспорт в SQLite/JSON/Luau; кнопка перестаёт быть зелёной. Отдельного Studio asset sync не требуется; при активном Rojo перезапустить Play и проверить новые стартовые атрибуты вновь созданного персонажа.
3. Изменить display name: Save Identity активируется; без изменений заблокирована. Переименование ID/race/gender — только после резервной копии и явного подтверждения.
4. Новый архетип: Reg + Publish → native FBX picker → модальный отчёт Validate/Register/Publish/Studio, каждый со своим исходом. Для уже опубликованного: выбор replacement FBX → **новый** Asset ID; старый ID сохранён до публикации.
5. Studio Bridge выключен (отдельный контролируемый негативный сценарий): после успешной публикации отчёт обязан показывать новый ID, не писать `Studio synced`, предлагать Retry; затем при включённом Bridge Retry не должен перепубликовать FBX.
6. Set as Startup отмечает выбранный архетип; новая Play-сессия использует его как default. У текущего startup повторная кнопка не активна.
7. Запустить `python system/verify/verify.py`, `python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q`, `node --check system/control-center/static/character-assets.js`, `node --check system/control-center/static/character-workflow.js`.

# M459 · Character Social Animation + M458 SQLite fixture

## Единые жесты Game1 / Character Creation

Добавлен отдельный `social` scope (не лицевые `emotions` и не боевой `attack`).
В игре и в сцене создания используем **те же опубликованные Animation ID** через CharacterAnimationRegistry:

| Имя исходника | Пол | Семантика |
| --- | --- | --- |
| `human_male_social_waiting_a.rbxm` | Male | Разминка (одноразовая) |
| `human_female_social_waiting_a.rbxm` | Female | Разминка (одноразовая) |
| `human_male_social_clap.rbxm` | Male | Аплодисменты |
| `human_female_social_clap.rbxm` | Female | Аплодисменты |
| `human_male_social_atk.rbxm` | Male | В бой, меч вперёд на 45° |
| `human_male_social_victory.rbxm` | Male | Победа, меч вверх |
| `human_female_social_atk.rbxm` | Female | В бой, меч вперёд на 45° |
| `human_female_social_victory.rbxm` | Female | Победа, меч вверх |
| `human_male_social_yes.rbxm` | Male | Согласие |
| `human_female_social_yes.rbxm` | Female | Согласие |
| `human_male_social_bow.rbxm` | Male | Поклон |
| `human_female_social_bow.rbxm` | Female | Поклон |
| `human_male_social_laugh.rbxm` | Male | Смех |
| `human_female_social_laugh.rbxm` | Female | Смех |
| `human_male_social_hi.rbxm` | Male | Приветствие |
| `human_female_social_hi.rbxm` | Female | Приветствие |
| `human_male_social_sad.rbxm` | Male | Грусть |
| `human_female_social_sad.rbxm` | Female | Грусть |

M463: добавлен `sad` (полнотелая социальная анимация, не лицевая `emotions.sad`) для обоих полов. Итого девять Social-действий и 18 семантических слотов. Никаких фиктивных Animation ID или дополнительных runtime-таблиц.

M462: добавлены `yes`, `bow`, `laugh`, `hi` для обоих полов. `clap` уже был в M459. Всего восемь действий и 16 семантических слотов (не Animation ID). Клиентский SocialAnimationPlayback больше не дублирует список имен: допустимые клипы определяются опубликованными записями `CharacterAnimationRegistry`.

M460: **все Social-действия обязательны как семантические слоты для обоих полов**; при добавлении нового Social-действия каталог автоматически показывает отдельный слот Male и Female. Нет гендерных исключений в списке Social.

Слоты **не являются анимациями**: для воспроизведения нужны настоящие RBXM/RBXMX и их публикация. Пустые слоты не попадают в Runtime Registry и не создают фиктивных Asset ID.

### Владелец данных

- `animation_core.common`: имена, определения, one-shot политика, поддерживаемые полы.
- `animation_core.storage`: сканирование/регистрация в существующей SQLite, исходники в `animations/social`.
- `animation_core.registry`: добавочное поле `profiles[].social` в генерируемых JSON/Luau; schemaVersion=2 без миграции.
- `AnimationResolver` / `CharacterStandAnimationCatalog`: чтение `social` и включение в prewarm и Studio test stand.
- `SocialAnimationPlayback`: малый presentation-only адаптер `Resolve/new/Play/Stop/Destroy` для будущего игрового меню социальных действий и сцены. Не управляет боем, не обходит Animator и не создаёт удалённых команд.

`human_male` отсутствует в текущем дампе в `characters`: перед назначением ему клипов нужна регистрация мужской базы. Сцена Character Creation и меню социальных действий ещё не реализованы, так что событие выбора пола пока не проигрывает клип автоматически. Для `social_atk`/`social_victory` нужен визуально экипированный меч — код клипа его не создаёт.

### Исправление Windows

`test_m458_armor_gender_pair_readiness.py` закрывает оба `sqlite3.connect` из процедуры backup через `contextlib.closing`. `with sqlite3.connect` **не закрывает** соединение; поэтому Windows выдавал WinError 32 при `TemporaryDirectory.cleanup`. Боевые/авторские SQLite сервисы не затронуты.

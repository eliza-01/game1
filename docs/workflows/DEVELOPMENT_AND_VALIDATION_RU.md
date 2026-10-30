# game1 — практический workflow разработки и проверки

**Актуализация:** 30.10.2026. Команды выполнять из корня `game1`; это документация, не скрипт автоматического запуска.

## Локальный контур

| Назначение | Команда / путь | Контракт |
| --- | --- | --- |
| Первичная подготовка | `./bootstrap.ps1` | только отдельный проект, не поверх RobloxLineage |
| Основной Control Center | `./control-center.ps1` | HTTP `127.0.0.1:43820` по текущему README/config |
| Host Agent | `system/control-center/host_agent.py` | `127.0.0.1:43821` по default, контролируемый токен/доступ |
| Rojo sync | `./sync.ps1` | `127.0.0.1:34882` в текущем baseline |
| Studio Bridge | `system/studio-plugin/install.ps1` | сборка+Luau проверка+установка актуального плагина |
| Сцена | `place/game1.rbxl` | объекты Workspace управляются автором; Rojo не перезаписывает их трансформации |

Точные настройки допускают изменение через конфигурацию и переменные окружения. Нельзя считать ports или established plugin state в чужой Studio автоматически совпадающими с dump.

## Проверка и поставка патча

```powershell
python system/verify/verify.py
python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q
python system/studio-plugin/validate_luau.py
```

Для затронутого JS запускать `node --check <файл>`. Для FBX: headless Blender prepare + export + reimport, проверка rest matrices, vertices, dimensions и skin; отдельно Roblox Studio model load/Play. Для Open Cloud/SQLite — dry-run либо копия БД, comparison SHA/IDs. Проверки Blender и UI нельзя подменять статическими assertion по строкам.

Для модульных изменений `system/verify` (R2) обязательны: совпадение нормального вывода `verify.py` с базой, успешные `unittest`, целевые негативные сценарии изменённого валидатора. **Ручная проверка для R2:** запустить одну команду `python system/verify/verify.py` на своей рабочей копии — ожидать `verify ok`, отсутствие новых ложных сообщений и изменений данных. Studio/Control Center перезапускать не нужно, если менялся только `system/verify` и документация. После каждого патча приводить отдельный список обязательных/рекомендованных проверок, их ожидаемых результатов и непроверенных Studio-only сценариев.

**Патч:** `git -c core.autocrlf=true apply --check <path>` → `git -c core.autocrlf=true apply <path>`. При успешном `git apply` отсутствие вывода нормально. После применения проверить `git status --short` и перезапустить только затронутый сервис. На Windows команды `git apply` используют относительные пути от **корня** проекта. Логи тестов/Studio в handoff отделять от предположений.

## Минимальные сценарии Studio для регрессий

- **Character / combat:** move/sprint/backpedal/attack, multiple hitbox victims, headshot/corpse, death/respawn, экипировка, animation transition/speed.
- **NPC / monster:** idle/chase/attack/return/death/respawn, отсутствие freeze на последнем кадре, cleanup subscriptions.
- **Real Estate:** исходный размер house/door/col_mesh, published skinned bones, door optional, ServerStorage template, placed clone and scoped/full Sync, отсутствие `Parent property locked` после Undo.
- **House sockets:** ключ OWN/LOST, E/F у обеих ручек, дверь при движении, оба floor spawn, AIM/USE у лифта и сундука, препятствия raycast, camera inside AIM, оба типа персонажей.
- **Atlases:** новая публикация варианта, reuse одного Image Asset ID у нескольких consumers, legacy owner/reuse, sync revision acknowledgement, отсутствие ложного UPDATE_AVAILABLE; не менять pivot/geometries у placed models.

## Безопасность данных и откат

Перед schema, publication или массовой Studio Sync операцией: snapshot `.control-center/*.db`, `assets/manifests`, выбранных source/prepared и registry. Не коммитить API ключи, токены, секреты и тяжёлые Blender/Roblox meshes в диагностические архивы. Любой rollback БД после новых публикаций может потерять связи с новыми ID — сначала провести сверку, а не вслепую восстанавливать SQLite.

## Документация при каждом изменении

Обновить только затронутые разделы текущего ТЗ/архитектуры. Исторический отчёт milestone хранить как snapshot с исходными наблюдениями. См. [правила документации](DOCUMENTATION_RULES_RU.md).

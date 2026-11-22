# Location Assets · LOD distance workflow

Настраивайте индивидуальные дистанции и режимы в **LOD Manager → LOD readiness**.
Используются единый `LocationLodDistancePolicy` и существующий
`LocationWorldStreamer`. Сохранённый профиль автоматически применяется
к Studio Play через `StudioLodPreviewAdapter`; при сборке Runtime параметры
фиксируются в отдельном манифесте.

Отладочные BillboardGui, HUD со счётчиками FULL/LOD и отдельный Studio LOD Probe
удалены в M434. Само переключение визуальных состояний, гистерезис,
проверки наличия моделей и ошибки загрузки остались рабочими.

Для проверки: в Studio Play отойдите от ассета на его индивидуальную
дистанцию UNLOADED, затем вернитесь. Проверьте возвращение FULL/LOD1 и
неизменность коллизии. Для Runtime необходимо собрать новый draft.

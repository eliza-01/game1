# M264 · Допуск проверки placement после ScaleTo/PivotTo

`StudioLocationPlacedGeometry` сохраняет CFrame, Size и PivotOffset старого
визуального MeshPart при полной замене legacy child rig. Roblox может вернуть
малую floating-point погрешность после `Model:ScaleTo` и `Model:PivotTo`, поэтому
точное сравнение CFrame ошибочно блокировало безопасно выровненный stage.

Проверка позиции и осей теперь использует тот же предел, что общий
`StudioManagedRigSwap`: не более 0.025 studs и dot осей не менее 0.9999.
Допуск Size остаётся 0.025. Проверка выполняется на staging-модели до commit;
выход за пределы по-прежнему отменяет всю scoped-операцию без изменения Place.

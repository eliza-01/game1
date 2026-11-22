--!strict
local Config = {
    FuelDurationSeconds = 120,
    EmbersDurationSeconds = 120,
    CookingSecondsOnFire = 30,
    CookingSecondsOnEmbers = 60,
    ProgressVisibleRadius = 50,
    ResourceSpend = table.freeze({
        Wood = table.freeze({icon = "wood", amount = 5, label = "Дерево"}),
        Carrot = table.freeze({icon = "carrot", amount = 1, label = "Морковка"}),
        Onion = table.freeze({icon = "onion", amount = 1, label = "Лук"}),
        Potato = table.freeze({icon = "potato", amount = 1, label = "Картофель"}),
    }),
    Fire = table.freeze({
        Size = 2.0,
        Heat = 3.0,
        TimeScale = 0.7,
        Primary = Color3.fromRGB(155, 125, 100),
        Secondary = Color3.fromRGB(255, 50, 60),
    }),
    Light = table.freeze({
        Enabled = true,
        Shadows = false,
        Brightness = 2.3,
        Range = 11.0,
        Color = Color3.fromRGB(255, 175, 70),
    }),
    Steam = table.freeze({
        Rate = 11,
        Lifetime = NumberRange.new(1.4, 2.4),
        Speed = NumberRange.new(1.6, 2.4),
        SpreadAngle = Vector2.new(5, 5),
        Acceleration = Vector3.new(0, 3.5, 0),
    }),
}
return table.freeze(Config)

-- Authoritative projectile policy. Visuals and gameplay share these constants.
-- No weapon catalog entries or animation IDs are synthesized here.
return table.freeze({
    DefaultSpeed = 145,          -- used only when no published arrow is active
    Gravity = 38,                -- studs / second^2 (gameplay arrow, not workspace gravity)
    MaxDistance = 420, -- safety cap matches the Weapon Range editor maximum
    MaxLifetime = 3.6,
    MaxActivePerPlayer = 3,
    MinSpawnDistance = 1.0,
    AimUpdateInterval = 0.10,
    ReleaseEvent = "Release", -- bow-specific authored timeline event, separate from melee HitStart/HitEnd
    MaxAimYaw = math.rad(145),
    MinAimPitch = math.rad(-75),
    MaxAimPitch = math.rad(75),
})

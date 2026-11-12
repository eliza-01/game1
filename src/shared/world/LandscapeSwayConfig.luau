-- Anchored, locally animated pendulums; no continuously simulated physics.
return table.freeze({
    Radius = 140,
    AmbientMaxTargets = 48,
    AmbientScanSeconds = 2.5,
    PresentationHz = 24,
    SettleSeconds = 1.8,
    AmbientAngle = math.rad(1.8),
    AmbientFrequency = 1.25,
    ImpactAngle = math.rad(13),
    WindAngle = math.rad(4),
    WindFrequency = 2,
    WindMaxTargets = 48,
    Duration = 6,
    Decay = 0.75,
    Frequency = 7.5,
    -- Supply a published wind Sound asset before enabling the sound.
    WindSoundId = "",
})

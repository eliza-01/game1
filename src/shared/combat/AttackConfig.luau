return table.freeze({
    Range = 7,
    BoxWidth = 5,
    BoxHeight = 5,
    MaxAimDistance = 420,

    -- RobloxLineage attack-facing contract. A planted attack can twist the upper
    -- body up to this yaw. Only the overflow is assigned to whole-character yaw.
    TorsoYawLimit = math.rad(70),
    TorsoAimResponse = 26,
    FacingTurnSeconds = 0.28,
    MovementLockSeconds = 0.22,
    AimPoseSeconds = 0.34,

    DebugLogs = true,
})

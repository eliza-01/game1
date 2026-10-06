return table.freeze({
    Range = 7,
    BoxWidth = 5,
    BoxHeight = 5,
    MaxAimDistance = 420,

    -- RobloxLineage attack-facing contract. A planted attack can twist the upper
    -- body up to this yaw. Only the overflow is assigned to whole-character yaw.
    TorsoYawLimit = math.rad(70),
    TorsoAimResponse = 26,
    -- Time used to rotate the root overflow toward the attack direction. The
    -- resulting facing is then held until the complete attack animation ends.
    FacingTurnSeconds = 0.28,

    -- RobloxLineage-style upper-body composition: legs stay on combat locomotion
    -- while the source attack animation drives only the spine subtree.
    UpperBodyAttackEntryBlendSeconds = 0.10,
    UpperBodyAttackExitBlendSeconds = 0.12,
    UpperBodyAttackTrackReadySeconds = 1.0,
    UpperBodyAttackTerminalLeadSeconds = 1 / 120,

    DebugLogs = true,
})

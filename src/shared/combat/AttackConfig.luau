return table.freeze({
    Range = 7,
    MaxAimDistance = 420,
    AttackRadiusEpsilon = 0.15,
    -- Head/body boxes are precomputed once from visual-mesh bounds. Arc
    -- contact deals normal melee damage; headshot is a separate live
    -- reticle-ray classification and can upgrade at most one target per attack.
    HeadshotDamageMultiplier = 2,
    HeadshotAimOriginMaxDistance = 24,

    -- M358: server samples the authored HitStart/HitEnd window independently
    -- of any client pose. Arc width is a per-weapon persisted setting.
    MeleeDefaultArcAngle = 108,
    MeleeVerticalPadding = 1.5,
    MeleeSampleInterval = 1 / 20,
    MeleeWindowGraceSeconds = 0.04,
    MaxMeleeAimWindowSeconds = 8,

    -- RobloxLineage attack-facing contract. A planted attack can twist the upper
    -- body up to this yaw. Only the overflow is assigned to whole-character yaw.
    TorsoYawLimit = math.rad(70),
    -- Bow strafing keeps the lower body aligned with travel while the upper
    -- bridge turns toward the camera (up to ~90 degrees for a sideways strafe).
    -- Planted shots continue to use the normal 70-degree limit + root overflow.
    MovingBowTorsoYawLimit = math.rad(100),
    TorsoAimResponse = 26,
    -- Local pitch is applied to the spine bridge after authored source poses.
    TorsoPitchUpLimit = math.rad(65),
    TorsoPitchDownLimit = math.rad(55),
    -- Downward camera pitch is softened only within point-blank melee reach.
    -- This avoids the head dipping into a nearby target, while allowing full
    -- vertical tracking again by 9 studs. Does not change weapon hit range.
    CloseAimPitchNeutralStuds = 3,
    CloseAimPitchFullStuds = 9,
    -- Stationary melee ramps root overflow over this time. The bow uses the
    -- same interval as its exponential live yaw response to a changing reticle.
    FacingTurnSeconds = 0.28,

    -- RobloxLineage-style upper-body composition: legs stay on combat locomotion
    -- while the source attack animation drives only the spine subtree.
    UpperBodyAttackEntryBlendSeconds = 0.10,
    UpperBodyAttackExitBlendSeconds = 0.12,
    UpperBodyAttackTrackReadySeconds = 1.0,
    UpperBodyAttackTerminalLeadSeconds = 1 / 120,

    DebugLogs = true,
})

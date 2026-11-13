-- Final pre-Release hitscan policy, plus cosmetic shot presentation budgets.
-- Damage is validated once on the server; only the clients animate arrow models.
return table.freeze({
    DefaultSpeed = 145,
    MaxDistance = 420,
    MinSpawnDistance = 1,
    CaptureLeadSeconds = 0.10,
    CaptureWindowSeconds = 0.50,
    CaptureGraceSeconds = 0.20,
    MaxLaunchOffset = 6,
    MaxLaunchSocketError = 4,
    ReleaseEvent = "Release",
    MaxAimYaw = math.rad(145),
    MinAimPitch = math.rad(-75),
    MaxAimPitch = math.rad(75),
    -- Hitscan line of sight is evaluated at Release from the verified nock.
    OcclusionTolerance = 0.08,
    -- Refine only one recorded contact, never run skinned-mesh casts per frame.
    VisualSurfaceTolerance = 1.25,
    VisualSurfaceSearchAhead = 0.85,
    VisualReplicationRadius = 220,
    MaxClientVisuals = 64,
    MaxVisualAttachmentJump = 3.0,
    StuckLifetime = 2.5,
    BoneFollowStep = 1 / 30,
})

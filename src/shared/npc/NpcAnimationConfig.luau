-- NPC presentation defaults, independent of individual NPC definitions.
return table.freeze({
    WeaponSet = "1hs",
    TransitionSeconds = 0.1,
    -- Begin returning from a one-shot special before its track loses its final pose.
    SpecialExitBlendSeconds = 0.15,
    -- Fallback cadence when there is no playable looping base idle.
    MissingBaseIdleCycleSeconds = 4,
    -- A missing/unavailable Roblox asset must not lock an NPC in a special forever.
    UnresolvedSpecialTimeoutSeconds = 8,
})

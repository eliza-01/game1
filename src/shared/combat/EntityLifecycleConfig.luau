local EntityLifecycleConfig = {}

-- One corpse-presentation contract for characters, monsters and future NPCs.
-- Death animation playback is owned by DeathAnimationPolicy. This timer starts
-- only after the final authored Death pose has been latched.
EntityLifecycleConfig.DeathIdleSurfaceSeconds = 3
EntityLifecycleConfig.DeathIdleSinkSeconds = 2
EntityLifecycleConfig.DeathIdleSeconds = EntityLifecycleConfig.DeathIdleSurfaceSeconds + EntityLifecycleConfig.DeathIdleSinkSeconds
EntityLifecycleConfig.CorpseSinkPaddingStuds = 0.5

return table.freeze(EntityLifecycleConfig)

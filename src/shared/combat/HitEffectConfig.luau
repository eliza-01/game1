local HitEffectConfig = {}

HitEffectConfig.RemoteName = "CombatHitEffect"
HitEffectConfig.ServerReplicationRadius = 160
HitEffectConfig.ClientRenderRadius = 120
HitEffectConfig.PoolSize = 4
HitEffectConfig.BurstCapacity = 12
HitEffectConfig.MaxBurstsPerSecond = 36

HitEffectConfig.NormalSparkCount = 5
HitEffectConfig.CriticalSparkCount = 8
HitEffectConfig.NormalSparkDuration = 0.10
HitEffectConfig.CriticalSparkDuration = 0.12
HitEffectConfig.SparkTravelSpeedMin = 8.5
HitEffectConfig.SparkTravelSpeedMax = 13.0
HitEffectConfig.SparkLengthMin = 0.42
HitEffectConfig.SparkLengthMax = 0.72
HitEffectConfig.SparkWidthTail = 0.052
HitEffectConfig.SparkWidthHead = 0.018
HitEffectConfig.SparkBrightness = 4.0
HitEffectConfig.SparkOriginSpreadX = 0.30
HitEffectConfig.SparkOriginSpreadY = 0.42
HitEffectConfig.SparkOriginDepth = 0.08
HitEffectConfig.SparkDirectionJitterDegrees = 10
HitEffectConfig.SparkDepthJitter = 0.12

HitEffectConfig.FrontFlashDuration = 0.085
HitEffectConfig.FrontFlashOffset = 1.8
HitEffectConfig.FrontFlashBrightness = 4.0
HitEffectConfig.FrontFlashCriticalMultiplier = 1.35
HitEffectConfig.FrontFlashRange = 8
HitEffectConfig.FrontFlashAngle = 110
HitEffectConfig.FallbackTargetOffsetY = 2.25

return table.freeze(HitEffectConfig)

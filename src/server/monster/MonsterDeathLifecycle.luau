-- M91: terminal death presentation and handoff to shared corpse sinking lifecycle.
-- MonsterSpawnerService retains ownership of population slots and respawn scheduling.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local AnimationSpeedScaling = require(Shared:WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))
local DeathAnimationPolicy = require(Shared:WaitForChild("combat"):WaitForChild("DeathAnimationPolicy"))
local DeathLifecycleService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("DeathLifecycleService"))

local MonsterDeathLifecycle = {}

function MonsterDeathLifecycle.new(callbacks: any): any
    local stopWanderMovement = callbacks.stopWanderMovement
    local stopIdleState = callbacks.stopIdleState
    local stopTrack = callbacks.stopTrack
    local releaseInstance = callbacks.releaseInstance

    local function enterDeathIdle(state: any, model: Model, entry: any)
        if entry.deathPoseHeld or state.instances[model] ~= entry or not model.Parent then
            return
        end
        entry.deathPoseHeld = true
        model:SetAttribute("MonsterAnimationState", "death_idle")
        model:SetAttribute("DeathTerminalPoseHeld", true)
        model:SetAttribute("DeathTerminalPoseHeldAt", os.clock())
        local started = DeathLifecycleService.BeginDeathIdle(model, entry.navigationRoot, entry.visual, function()
            releaseInstance(state, model, true)
        end)
        assert(started, "DeathIdle lifecycle must start exactly once after the terminal Death pose")
    end

    local function maintainDeathTerminalPose(state: any, model: Model, entry: any, deltaTimeSim: number)
        if not entry.dying
            or entry.deathPoseHeld
            or state.instances[model] ~= entry
            or not model.Parent
            or tostring(model:GetAttribute("LifeState") or "") ~= "Dying"
        then
            return
        end

        local track = entry.deathTrack
        if not track then
            return
        end

        local reached, terminalTime = DeathAnimationPolicy.LatchVisibleTerminalPose(track, deltaTimeSim)
        if not reached then
            return
        end

        model:SetAttribute("DeathAnimationLength", track.Length)
        model:SetAttribute("DeathAnimationTerminalTime", terminalTime)
        enterDeathIdle(state, model, entry)
    end

    local function beginDeath(state: any, model: Model, entry: any)
        if entry.dying then
            return
        end
        entry.dying = true
        entry.deathPoseHeld = false
        model:SetAttribute("Damageable", false)
        model:SetAttribute("MonsterAnimationState", "death")
        model:SetAttribute("MonsterIdleVariant", nil)
        model:SetAttribute("DeathAnimationStartedAt", os.clock())
        model:SetAttribute("DeathTerminalPoseHeld", false)
        stopWanderMovement(entry)
        stopIdleState(entry)
        stopTrack(entry.combatIdleTrack)
        if entry.navigationRoot and entry.navigationRoot.Parent then
            entry.navigationRoot.AssemblyLinearVelocity = Vector3.zero
            entry.navigationRoot.AssemblyAngularVelocity = Vector3.zero
            entry.navigationRoot.Anchored = true
        end

        local track = entry.deathTrack
        if not track then
            warn("[game1][monster-spawn] required death animation track is missing; monster remains Dying")
            return
        end
        model:SetAttribute("AnimationPlaybackSpeedPercent", AnimationSpeedScaling.ResolveForAnimation(model, "death", track.Animation and track.Animation.AnimationId))
        DeathAnimationPolicy.Start(track, AnimationSpeedScaling.ResolveScaleForAnimation(model, "death", track.Animation and track.Animation.AnimationId))
    end


    local lifecycle = {}
    function lifecycle:Begin(state: any, model: Model, entry: any)
        beginDeath(state, model, entry)
    end
    function lifecycle:Maintain(state: any, model: Model, entry: any, deltaTimeSim: number)
        maintainDeathTerminalPose(state, model, entry, deltaTimeSim)
    end
    return table.freeze(lifecycle)
end

return table.freeze(MonsterDeathLifecycle)

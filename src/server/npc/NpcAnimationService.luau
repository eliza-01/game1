-- NPC actor animation state machine: peace/combat/death transitions only.
-- Idle weights, clip loading and spawn quotas are owned by separate modules.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local DeathAnimationPolicy = require(Shared:WaitForChild("combat"):WaitForChild("DeathAnimationPolicy"))
local AnimationSpeedScaling = require(Shared:WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))
local NpcIdlePresentation = require(script.Parent:WaitForChild("NpcIdlePresentation"))
local Tracks = require(script.Parent:WaitForChild("NpcAnimationTracks"))

local NpcAnimationService = {}

function NpcAnimationService.Create(entity: Model, visual: Model, profile: any?): any
    local controller = visual:FindFirstChildOfClass("AnimationController")
        or visual:FindFirstChildWhichIsA("AnimationController", true)
    if not controller then
        controller = Instance.new("AnimationController")
        controller.Name = "AnimationController"
        controller.Parent = visual
    end
    for _, child in ipairs(entity:GetDescendants()) do
        if child:IsA("AnimationController") and child ~= controller then
            child:Destroy()
        end
    end
    local animator = controller:FindFirstChildOfClass("Animator")
    if not animator then
        animator = Instance.new("Animator")
        animator.Parent = controller
    end

    local function first(slot: string): any?
        return Tracks.PublishedRows(profile, slot)[1]
    end
    local idle = NpcIdlePresentation.new(entity, animator, profile)
    local combatIdle = Tracks.Load(animator, first("combat_idle"), true)
    -- DeathAnimationPolicy owns the terminal pose; a loop seam is not used for death.
    local deathClip = Tracks.Load(animator, first("death"), false, false)
    local death = deathClip and deathClip.track or nil
    local dying = false
    local finished = false
    local disposed = false
    local deathStartedAt = 0

    local function syncState()
        if dying or disposed then
            return
        end
        if entity:GetAttribute("InCombat") == true then
            idle:Stop()
            entity:SetAttribute("NpcAnimationState", "combat_idle")
            if combatIdle then
                Tracks.Play(entity, combatIdle, "combat_idle")
            end
        else
            Tracks.Stop(combatIdle)
            idle:Start()
        end
    end

    local function beginDeath()
        if dying or disposed then
            return
        end
        dying = true
        deathStartedAt = os.clock()
        idle:Stop()
        Tracks.Stop(combatIdle)
        entity:SetAttribute("NpcAnimationState", "death")
        entity:SetAttribute("DeathAnimationStartedAt", deathStartedAt)
        if death then
            DeathAnimationPolicy.Start(death, AnimationSpeedScaling.ResolveForModel(entity, "death") / 100)
        end
    end

    local function step(delta: number): boolean
        if disposed then
            return false
        end
        if not dying then
            idle:Step(delta)
            if entity:GetAttribute("InCombat") == true then
                Tracks.Step(combatIdle, delta)
            end
            return false
        end
        if finished then
            return false
        end
        if not death then
            finished = true
            return true
        end
        local reached, terminalTime = DeathAnimationPolicy.LatchVisibleTerminalPose(death, delta)
        if not reached and death.Length <= 0 and os.clock() - deathStartedAt >= 8 then
            warn("[game1][npc] unresolved death animation; releasing corpse lifecycle: " .. entity.Name)
            finished = true
            return true
        end
        if reached then
            finished = true
            entity:SetAttribute("DeathAnimationLength", death.Length)
            entity:SetAttribute("DeathAnimationTerminalTime", terminalTime)
            entity:SetAttribute("DeathTerminalPoseHeld", true)
            return true
        end
        return false
    end

    local changed = entity:GetAttributeChangedSignal("InCombat"):Connect(syncState)
    local function destroy()
        if disposed then
            return
        end
        disposed = true
        changed:Disconnect()
        idle:Destroy()
        Tracks.Stop(combatIdle)
        Tracks.Stop(deathClip)
    end

    syncState()
    return { BeginDeath = beginDeath, Step = step, Destroy = destroy }
end

return table.freeze(NpcAnimationService)

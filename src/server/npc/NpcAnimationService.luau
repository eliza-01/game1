-- NPC presentation state machine. Combat AI owns decisions; this module owns tracks.
-- Equipment remains attached in every state. Only an authored idle_special with
-- disarm=true may request a temporary weapon-visibility override.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local DeathAnimationPolicy = require(Shared:WaitForChild("combat"):WaitForChild("DeathAnimationPolicy"))
local AnimationSpeedScaling = require(Shared:WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))
local WeaponPresentationState = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponPresentationState"))
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
        if child:IsA("AnimationController") and child ~= controller then child:Destroy() end
    end
    local animator = controller:FindFirstChildOfClass("Animator")
    if not animator then
        animator = Instance.new("Animator")
        animator.Parent = controller
    end

    local weaponSet = tostring(entity:GetAttribute("NpcWeaponSet") or "1hs")
    local function first(slot: string): any?
        return Tracks.PublishedRows(profile, slot, weaponSet)[1]
    end
    local weaponPresentation = WeaponPresentationState.new(entity)
    local idle = NpcIdlePresentation.new(entity, animator, profile, weaponSet, weaponPresentation)
    local combatIdle = Tracks.Load(animator, first("combat_idle") or first("idle"), true)
    local runRow = first("run") or first("walk")
    local movementChannel = if first("run") then "run" else "walk"
    local run = Tracks.Load(animator, runRow, true)
    local deathClip = Tracks.Load(animator, first("death"), false, false)
    local death = deathClip and deathClip.track or nil
    local attackClips: {[string]: any} = {}
    local dying, finished, disposed = false, false, false
    local attacking, moving, returning, returnMoving = false, false, false, false
    local combatActive = false
    local deathStartedAt = 0

    for _, row in ipairs(Tracks.PublishedRows(profile, "attack", weaponSet)) do
        local clip = Tracks.Load(animator, row, true, false)
        if clip then attackClips[tostring(row.clipId or row.animationId)] = clip end
    end
    local currentAttack: any? = nil

    local function stopCombatTracks()
        Tracks.Stop(combatIdle)
        Tracks.Stop(run)
    end

    local function syncState()
        if dying or disposed then return end
        if returning then
            -- ReturnWait and Return are one lifecycle state: idle_special must
            -- remain disabled until the authored spawn pose is restored.
            idle:Stop()
            if returnMoving then
                Tracks.Stop(combatIdle)
                entity:SetAttribute("NpcAnimationState", "run")
                Tracks.Play(entity, run, movementChannel)
            else
                Tracks.Stop(run)
                entity:SetAttribute("NpcAnimationState", "combat_idle")
                Tracks.Play(entity, combatIdle, "combat_idle")
            end
        elseif combatActive then
            idle:Stop()
            if attacking then return end
            if moving then
                Tracks.Stop(combatIdle)
                entity:SetAttribute("NpcAnimationState", "run")
                Tracks.Play(entity, run, movementChannel)
            else
                Tracks.Stop(run)
                entity:SetAttribute("NpcAnimationState", "combat_idle")
                Tracks.Play(entity, combatIdle, "combat_idle")
            end
        else
            attacking = false
            moving = false
            Tracks.Stop(currentAttack)
            currentAttack = nil
            stopCombatTracks()
            idle:Start()
        end
    end

    local function setCombatActive(value: boolean)
        if dying or disposed or combatActive == value then return end
        combatActive = value
        syncState()
    end

    local function setCombatMoving(value: boolean)
        if dying or disposed then return end
        if moving == value then return end
        moving = value
        syncState()
    end

    local function setReturnActive(value: boolean)
        if dying or disposed or returning == value then return end
        returning = value
        if not returning then returnMoving = false end
        syncState()
    end

    local function setReturnMoving(value: boolean)
        if dying or disposed or returnMoving == value then return end
        returnMoving = value
        syncState()
    end

    local function startAttack(row: any?, speedPercent: number?): (boolean, AnimationTrack?)
        if dying or disposed then return false, nil end
        -- The action state is valid even if no optional attack animation was published.
        attacking = true
        idle:Stop()
        stopCombatTracks()
        Tracks.Stop(currentAttack)
        currentAttack = row and attackClips[tostring(row.clipId or row.animationId)] or nil
        entity:SetAttribute("NpcAnimationState", "attack")
        if currentAttack then Tracks.Play(entity, currentAttack, "attack", nil, speedPercent) end
        -- The owning AI schedules Hit and completion; expose the SAME loaded
        -- track so fallback timing follows the actual published clip length.
        return true, if currentAttack then currentAttack.track else nil
    end

    -- Keep one looped attack track alive while the target stays in range.
    -- Each damage cycle is owned by the AI; animation is not restarted after Hit.
    local function continueAttack(speedPercent: number?)
        if dying or disposed or not attacking or not currentAttack then return end
        Tracks.Play(entity, currentAttack, "attack", nil, speedPercent)
    end

    local function endAttack()
        if not attacking then return end
        attacking = false
        Tracks.Stop(currentAttack)
        currentAttack = nil
        syncState()
    end

    local function beginDeath()
        if dying or disposed then return end
        dying = true
        deathStartedAt = os.clock()
        attacking = false
        idle:Stop()
        stopCombatTracks()
        Tracks.Stop(currentAttack)
        currentAttack = nil
        -- Do not disarm, detach or drop equipment at death.
        entity:SetAttribute("NpcAnimationState", "death")
        entity:SetAttribute("DeathAnimationStartedAt", deathStartedAt)
        if death then DeathAnimationPolicy.Start(death, AnimationSpeedScaling.ResolveForModel(entity, "death") / 100) end
    end

    local function step(delta: number): boolean
        if disposed then return false end
        if not dying then
            idle:Step(delta)
            if combatActive or returning then
                Tracks.Step(combatIdle, delta)
                Tracks.Step(run, delta)
            end
            return false
        end
        if finished then return false end
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

    local changedRun = entity:GetAttributeChangedSignal("RunSpeed"):Connect(function()
        if not attacking then syncState() end
    end)
    local changedAttack = entity:GetAttributeChangedSignal("AttackSpeed"):Connect(function()
        if not attacking then syncState() end
    end)
    local function destroy()
        if disposed then return end
        disposed = true
        changedRun:Disconnect()
        changedAttack:Disconnect()
        idle:Destroy()
        weaponPresentation:Destroy()
        stopCombatTracks()
        Tracks.Stop(currentAttack)
        Tracks.Stop(deathClip)
        for _, clip in pairs(attackClips) do Tracks.Stop(clip) end
    end
    syncState()
    return {
        BeginDeath = beginDeath, Step = step, Destroy = destroy,
        SetCombatActive = setCombatActive, SetCombatMoving = setCombatMoving,
        SetReturnActive = setReturnActive, SetReturnMoving = setReturnMoving,
        StartAttack = startAttack, ContinueAttack = continueAttack, EndAttack = endAttack,
    }
end

return table.freeze(NpcAnimationService)

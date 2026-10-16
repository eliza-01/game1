-- Server-authoritative presentation of monster combat animations.
-- Owns published animation rows, track lifetimes, speed scaling and animation attributes.
-- Does not select targets, own AI states, calculate navigation, or apply damage.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local MonsterAnimationRegistry = require(Shared:WaitForChild("monster"):WaitForChild("MonsterAnimationRegistry"))
local AnimationSpeedScaling = require(Shared:WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))

local MonsterCombatPresentation = {}
local ATTACK_PURSUIT_PLAYBACK_EPSILON = 0.02
local DEFAULT_PURSUIT_MULTIPLIER = 1.65

local function finite(value: any, fallback: number): number
    local n = tonumber(value)
    if n == nil or n ~= n or n == math.huge or n == -math.huge then return fallback end
    return n
end

function MonsterCombatPresentation.PublishedRows(slug: string, slot: string): {any}
    local profile = MonsterAnimationRegistry.profiles and MonsterAnimationRegistry.profiles[slug]
    local rows = profile and profile.slots and profile.slots[slot]
    local result = {}
    for _, row in ipairs(typeof(rows) == "table" and rows or {}) do
        if tostring(row.animationId or ""):match("^rbxassetid://%d+$") then
            table.insert(result, row)
        end
    end
    return result
end

function MonsterCombatPresentation.WeightedRow(rows: {any}, random: Random): any?
    local total = 0
    for _, row in ipairs(rows) do total += math.max(1, finite(row.weight, 100)) end
    if total <= 0 then return rows[1] end
    local roll = random:NextNumber(0, total)
    local cursor = 0
    for _, row in ipairs(rows) do
        cursor += math.max(1, finite(row.weight, 100))
        if roll <= cursor then return row end
    end
    return rows[#rows]
end

local function animationPriority(value: any): Enum.AnimationPriority
    local name = tostring(value or "")
    if name == "Idle" then return Enum.AnimationPriority.Idle end
    if name == "Movement" then return Enum.AnimationPriority.Movement end
    if name == "Action2" then return Enum.AnimationPriority.Action2 end
    if name == "Action3" then return Enum.AnimationPriority.Action3 end
    if name == "Action4" then return Enum.AnimationPriority.Action4 end
    return Enum.AnimationPriority.Action
end

function MonsterCombatPresentation.AnimatorOf(model: Model): Animator?
    local animator = model:FindFirstChildWhichIsA("Animator", true)
    return if animator and animator:IsA("Animator") then animator else nil
end

function MonsterCombatPresentation.LoadTrack(animator: Animator, row: any, looped: boolean): AnimationTrack?
    local animationId = tostring(row and row.animationId or "")
    if not animationId:match("^rbxassetid://%d+$") then return nil end
    local animation = Instance.new("Animation")
    animation.AnimationId = animationId
    local ok, result = pcall(function() return animator:LoadAnimation(animation) end)
    animation:Destroy()
    if not ok then
        warn("[game1][monster-ai] animation load failed: " .. tostring(result))
        return nil
    end
    local track = result :: AnimationTrack
    track.Looped = looped
    track.Priority = animationPriority(row.priority)
    return track
end

local function stopTrack(track: AnimationTrack?, fade: number?)
    if track and track.IsPlaying then pcall(function() track:Stop(fade or 0.08) end) end
end

function MonsterCombatPresentation.Stop(agent: any)
    stopTrack(agent.runTrack)
    stopTrack(agent.combatIdleTrack)
    stopTrack(agent.attackTrack)
    agent.attackTrack = nil
end

function MonsterCombatPresentation.PlayCombatIdle(agent: any)
    if agent.attacking or not agent.active then return end
    stopTrack(agent.runTrack)
    stopTrack(agent.attackTrack)
    local track = agent.combatIdleTrack
    if track then
        local speed = AnimationSpeedScaling.ResolveScaleForAnimation(agent.model, "combat_idle", agent.combatIdleTrack and agent.combatIdleTrack.Animation and agent.combatIdleTrack.Animation.AnimationId)
        if track.IsPlaying then track:AdjustSpeed(speed) else track:Play(0.08, 1, speed) end
    end
    agent.model:SetAttribute("MonsterAnimationState", "combat_idle")
end

function MonsterCombatPresentation.PlayRun(agent: any, pursuitMultiplier: number?)
    if agent.attacking then
        -- During active attack the full-body attack keeps ownership. A client
        -- compositor samples Run and writes only the lower-body bones.
        return
    end
    stopTrack(agent.combatIdleTrack)
    stopTrack(agent.attackTrack)
    local track = agent.runTrack
    if track then
        local speed = AnimationSpeedScaling.ResolveScaleForAnimation(agent.model, "run", agent.runTrack and agent.runTrack.Animation and agent.runTrack.Animation.AnimationId) * math.max(1, pursuitMultiplier or 1)
        if track.IsPlaying then track:AdjustSpeed(speed) else track:Play(0.08, 1, speed) end
    end
    agent.model:SetAttribute("MonsterAnimationState", "run")
end


local function attackPursuitPlaybackSpeed(agent: any, movementMultiplier: number?): number
    return AnimationSpeedScaling.ResolveScaleForAnimation(agent.model, "run", agent.runTrack and agent.runTrack.Animation and agent.runTrack.Animation.AnimationId) * math.max(0.01, movementMultiplier or DEFAULT_PURSUIT_MULTIPLIER)
end

function MonsterCombatPresentation.PublishAttackPursuitPlaybackSpeed(agent: any, movementMultiplier: number?)
    local desired = attackPursuitPlaybackSpeed(agent, movementMultiplier)
    local current = tonumber(agent.model:GetAttribute("MonsterAttackPursuitPlaybackSpeed"))
    if current == nil or math.abs(current - desired) > ATTACK_PURSUIT_PLAYBACK_EPSILON then
        agent.model:SetAttribute("MonsterAttackPursuitPlaybackSpeed", desired)
    end
end


function MonsterCombatPresentation.Initialize(agent: any, runRow: any?, random: Random, pursuitMultiplier: number)
    if runRow then
        agent.model:SetAttribute("MonsterRunAnimationId", tostring(runRow.assetId or tostring(runRow.animationId):match("(%d+)$") or ""))
        agent.model:SetAttribute("MonsterAnimationPhase", random:NextNumber(0, 0.999))
        MonsterCombatPresentation.PublishAttackPursuitPlaybackSpeed(agent, pursuitMultiplier)
    end
end

function MonsterCombatPresentation.PlayAttack(agent: any, row: any, percent: number)
    stopTrack(agent.runTrack)
    stopTrack(agent.combatIdleTrack)
    stopTrack(agent.attackTrack)
    agent.attackTrack = MonsterCombatPresentation.LoadTrack(agent.animator, row, false)
    if agent.attackTrack then agent.attackTrack:Play(0.05, 1, math.max(0.01, percent / 100)) end
    agent.model:SetAttribute("MonsterAnimationState", "attack")
    agent.model:SetAttribute("AnimationPlaybackSpeedPercent", percent)
    agent.model:SetAttribute("MonsterAttackClipId", tostring(row.clipId or ""))
end

function MonsterCombatPresentation.StopAttack(agent: any)
    stopTrack(agent.attackTrack)
    agent.attackTrack = nil
end

return table.freeze(MonsterCombatPresentation)

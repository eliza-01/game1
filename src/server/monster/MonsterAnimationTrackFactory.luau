-- Loads one native AnimationTrack per published monster clip.
-- The caller owns playback state, connections, cleanup, AI and death.
local MonsterAnimationTrackFactory = {}
local function finite(value: any, fallback: number): number
    local number = tonumber(value)
    if number == nil or number ~= number or number == math.huge or number == -math.huge then
        return fallback
    end
    return number
end

local function publishedRows(profile: any?, slot: string): {any}
    local slots = profile and profile.slots
    local rows = slots and slots[slot]
    if typeof(rows) ~= "table" then
        return {}
    end
    local result = {}
    for _, row in ipairs(rows) do
        if tostring(row.animationId or ""):match("^rbxassetid://%d+$") then
            table.insert(result, row)
        end
    end
    return result
end

local function firstPublishedTrack(profile: any?, slot: string): any?
    return publishedRows(profile, slot)[1]
end

local function animatorFor(runtimeModel: Model, visual: Model): Animator
    -- Keep the animation host inside the visual rig, separate from the navigation
    -- Humanoid on the runtime wrapper. This mirrors the RobloxLineage contract:
    -- Humanoid owns locomotion of the wrapper; AnimationController owns the bones.
    local controller = visual:FindFirstChildOfClass("AnimationController")
        or visual:FindFirstChildWhichIsA("AnimationController", true)
        or runtimeModel:FindFirstChildOfClass("AnimationController")
        or runtimeModel:FindFirstChildWhichIsA("AnimationController", true)
    if not controller then
        controller = Instance.new("AnimationController")
        controller.Name = "AnimationController"
        controller.Parent = visual
    elseif controller.Parent ~= visual then
        controller.Parent = visual
    end

    for _, descendant in ipairs(runtimeModel:GetDescendants()) do
        if descendant:IsA("AnimationController") and descendant ~= controller then
            descendant:Destroy()
        end
    end

    local animator = controller:FindFirstChildOfClass("Animator")
    if not animator then
        animator = Instance.new("Animator")
        animator.Name = "Animator"
        animator.Parent = controller
    end
    return animator
end

local function animationPriority(value: any): Enum.AnimationPriority
    local name = tostring(value or "")
    if name == "Idle" then
        return Enum.AnimationPriority.Idle
    elseif name == "Movement" then
        return Enum.AnimationPriority.Movement
    elseif name == "Action2" then
        return Enum.AnimationPriority.Action2
    elseif name == "Action3" then
        return Enum.AnimationPriority.Action3
    elseif name == "Action4" then
        return Enum.AnimationPriority.Action4
    end
    return Enum.AnimationPriority.Action
end

local function loadAnimationTrack(animator: Animator?, row: any?, looped: boolean): AnimationTrack?
    if not animator or not row then
        return nil
    end
    local animationId = tostring(row.animationId or "")
    if not animationId:match("^rbxassetid://%d+$") then
        return nil
    end
    local animation = Instance.new("Animation")
    animation.AnimationId = animationId
    local ok, result = pcall(function()
        return animator:LoadAnimation(animation)
    end)
    animation:Destroy()
    if not ok then
        warn("[game1][monster-spawn] animation load failed: " .. tostring(result))
        return nil
    end
    local track = result :: AnimationTrack
    track.Looped = looped
    track.Priority = animationPriority(row.priority)
    return track
end

local function idleRole(row: any): string
    local role = tostring(row.role or "")
    if role ~= "" then
        return role
    end
    if tostring(row.sourceSlot or "") == "idle_special" or finite(row.variant, 0) > 0 then
        return "special"
    end
    return "base"
end


function MonsterAnimationTrackFactory.Load(profile: any?, runtimeModel: Model, visual: Model): any
    local animator = animatorFor(runtimeModel, visual)
    local idleTrack: AnimationTrack? = nil
    local idleChoices = {}
    for _, row in ipairs(publishedRows(profile, "idle")) do
        local role = idleRole(row)
        local track = loadAnimationTrack(animator, row, role == "base")
        if track then
            local choice = { row = row, track = track, role = role }
            table.insert(idleChoices, choice)
            if role == "base" and not idleTrack then
                idleTrack = track
            end
        end
    end
    local combatIdleRow = firstPublishedTrack(profile, "combat_idle") or firstPublishedTrack(profile, "idle")
    local walkRow = firstPublishedTrack(profile, "walk") or firstPublishedTrack(profile, "run")
    local runRow = firstPublishedTrack(profile, "run") or firstPublishedTrack(profile, "walk")
    local deathRow = firstPublishedTrack(profile, "death")
    local combatIdleTrack = loadAnimationTrack(animator, combatIdleRow, true)
    local walkTrack = loadAnimationTrack(animator, walkRow, true)
    local runTrack = loadAnimationTrack(animator, runRow, true)
    local deathTrack = loadAnimationTrack(animator, deathRow, false)
    local entry = {
        idleTrack = idleTrack,
        idleRow = nil,
        idleChoices = idleChoices,
        activeIdleSpecial = nil,
        combatIdleTrack = combatIdleTrack,
        combatIdleRow = combatIdleRow,
        walkTrack = walkTrack,
        walkRow = walkRow,
        runTrack = runTrack,
        runRow = runRow,
        deathTrack = deathTrack,
        deathRow = deathRow,
    }
    for _, choice in ipairs(idleChoices) do
        if choice.role == "base" and choice.track == idleTrack then
            entry.idleRow = choice.row
            break
        end
    end
    return entry
end
return table.freeze(MonsterAnimationTrackFactory)

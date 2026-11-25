--!strict
-- Preview-only social reactions. Idle keeps running underneath the one-shot.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("character")
local Registry = require(Shared:WaitForChild("CharacterAnimationRegistry"))
local Merge = require(Shared:WaitForChild("CharacterAnimationVariantMerge"))
local Reactions = {}
Reactions.__index = Reactions
local GROUPS = {"atk", "bow", "clap", "hi", "laugh", "sad", "sp_wait", "unaware", "victory", "waiting", "yes"}
local random = Random.new()
local FADE = 0.18

type Active = {track: AnimationTrack, animation: Animation, connection: RBXScriptConnection?}

-- Group weights are independent of the number of published variants. Within
-- the selected group every numbered, published variant has equal probability.
function Reactions.Pool(registry: any, archetype: string, weights: any): ({any}, number)
    local profile = (registry.profiles or {})[archetype]
    if not profile then return {}, 0 end
    local shared = (registry.shared or {})[profile.family or ""] or {}
    local result, total = {}, 0
    for _, group in ipairs(GROUPS) do
        if group == "bow" and archetype ~= "human_female" then continue end
        local weight = tonumber((weights or {})[group]) or 0
        if weight <= 0 then continue end
        local rows = {}
        for _, clip in ipairs(Merge.Rows((profile.social or {})[group], (shared.social or {})[group])) do
            if type(clip.animationId) == "string" and string.match(clip.animationId, "^rbxassetid://%d+$") then
                table.insert(rows, clip)
            end
        end
        if #rows > 0 then
            total += weight
            table.insert(result, {group = group, weight = weight, rows = rows})
        end
    end
    return result, total
end

function Reactions.Choose(pool: {any}, total: number, rng: Random): any?
    if total <= 0 then return nil end
    local cursor = rng:NextNumber(0, total)
    for _, entry in ipairs(pool) do
        cursor -= entry.weight
        if cursor <= 0 then return entry.rows[rng:NextInteger(1, #entry.rows)] end
    end
    return nil
end

function Reactions.new(settings: any)
    return setmetatable({settings = settings or {}, active = {} :: {[Model]: Active},
        pools = {} :: {[string]: any}}, Reactions)
end

function Reactions:Remove(model: Model)
    local active = self.active[model]
    if not active then return end
    self.active[model] = nil
    if active.connection then active.connection:Disconnect() end
    active.track:Stop(0)
    active.track:Destroy()
    active.animation:Destroy()
end

function Reactions:Play(model: Model, archetype: string)
    -- Do not pile up requests or interrupt a gesture on every rapid click.
    if self.active[model] or not model.Parent then return end
    local chance = math.clamp(tonumber(self.settings.chancePercent) or 0, 0, 100)
    if chance <= 0 or (chance < 100 and random:NextNumber(0, 100) >= chance) then return end
    local cached = self.pools[archetype]
    if not cached then
        local pool, total = Reactions.Pool(Registry, archetype, self.settings.weights)
        cached = {pool = pool, total = total}
        self.pools[archetype] = cached
    end
    local clip = Reactions.Choose(cached.pool, cached.total, random)
    local animator = model:FindFirstChildWhichIsA("Animator", true)
    if not clip or not animator then return end
    local animation = Instance.new("Animation")
    animation.Name = "CharacterCreationReaction"
    animation.AnimationId = clip.animationId
    local ok, track = pcall(function() return animator:LoadAnimation(animation) end)
    if not ok or not track then
        animation:Destroy()
        warn("[game1][character-creation] reaction load failed: " .. tostring(clip.clipId))
        return
    end
    track.Looped = false
    track.Priority = Enum.AnimationPriority.Action
    local active: Active = {track = track, animation = animation, connection = nil}
    self.active[model] = active
    active.connection = track.Ended:Connect(function()
        if self.active[model] == active then self:Remove(model) end
    end)
    local played = pcall(function() track:Play(FADE) end)
    if not played then self:Remove(model); return end
    -- A failed asset may never produce Ended. Free the slot, without blocking UI.
    task.delay(8, function()
        if self.active[model] == active and track.Length <= 0 then
            self:Remove(model)
            warn("[game1][character-creation] reaction not ready: " .. tostring(clip.clipId))
        end
    end)
end

function Reactions:Destroy()
    for model in pairs(self.active) do self:Remove(model) end
    table.clear(self.pools)
end
return Reactions

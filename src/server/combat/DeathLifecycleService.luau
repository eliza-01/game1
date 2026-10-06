local TweenService = game:GetService("TweenService")

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local Config = require(CombatShared:WaitForChild("EntityLifecycleConfig"))

local DeathLifecycleService = {}
local active: { [Model]: any } = {}

local function sinkDistance(visual: Model?): number
    if not visual or not visual.Parent then
        return 2
    end
    local ok, _, size = pcall(function()
        local cf, bounds = visual:GetBoundingBox()
        return cf, bounds
    end)
    if ok and typeof(size) == "Vector3" then
        return math.max(2, size.Y + Config.CorpseSinkPaddingStuds)
    end
    return 2
end

function DeathLifecycleService.Cancel(entity: Model?)
    if not entity then
        return
    end
    local record = active[entity]
    active[entity] = nil
    if record and record.tween then
        pcall(function() record.tween:Cancel() end)
    end
end

function DeathLifecycleService.BeginDeathIdle(
    entity: Model,
    root: BasePart,
    visual: Model?,
    onExpired: ((Model) -> ())?
): boolean
    if not entity.Parent or not root.Parent or active[entity] then
        return false
    end

    local record = {
        root = root,
        visual = visual,
        onExpired = onExpired,
        generation = os.clock(),
        tween = nil,
    }
    active[entity] = record

    entity:SetAttribute("LifeState", "DeathIdle")
    entity:SetAttribute("DeathIdleStartedAt", os.clock())
    entity:SetAttribute("DeathIdleDuration", Config.DeathIdleSeconds)
    entity:SetAttribute("DeathSinkStartedAt", nil)

    task.delay(Config.DeathIdleSurfaceSeconds, function()
        if active[entity] ~= record or not entity.Parent or not root.Parent then
            return
        end

        entity:SetAttribute("DeathSinkStartedAt", os.clock())
        local start = root.CFrame
        local distance = sinkDistance(visual)
        local tween = TweenService:Create(
            root,
            TweenInfo.new(Config.DeathIdleSinkSeconds, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut),
            { CFrame = start + Vector3.new(0, -distance, 0) }
        )
        record.tween = tween
        tween:Play()
        tween.Completed:Wait()

        if active[entity] ~= record then
            return
        end
        active[entity] = nil
        entity:SetAttribute("DeathIdleExpiredAt", os.clock())
        if type(onExpired) == "function" then
            onExpired(entity)
        end
    end)
    return true
end

return table.freeze(DeathLifecycleService)

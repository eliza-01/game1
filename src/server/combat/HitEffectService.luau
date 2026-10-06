local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local HitEffectConfig = require(CombatShared:WaitForChild("HitEffectConfig"))

local HitEffectService = {}
local started = false
local remote: UnreliableRemoteEvent? = nil
local localCenterByTarget = setmetatable({}, { __mode = "k" })

local function ensureRemoteFolder(): Folder
    local current = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if current and current:IsA("Folder") then
        return current
    end
    if current then current:Destroy() end
    local folder = Instance.new("Folder")
    folder.Name = "Game1Remotes"
    folder.Parent = ReplicatedStorage
    return folder
end

local function ensureRemote(): UnreliableRemoteEvent
    local folder = ensureRemoteFolder()
    local current = folder:FindFirstChild(HitEffectConfig.RemoteName)
    if current and current:IsA("UnreliableRemoteEvent") then
        return current
    end
    if current then current:Destroy() end
    local created = Instance.new("UnreliableRemoteEvent")
    created.Name = HitEffectConfig.RemoteName
    created.Parent = folder
    return created
end

local function rootOf(model: Model?): BasePart?
    if not model then return nil end
    local root = model:FindFirstChild("RootCollider")
        or model:FindFirstChild("HumanoidRootPart")
        or model.PrimaryPart
    return if root and root:IsA("BasePart") then root else nil
end

local function targetPosition(target: Model, explicit: any): Vector3?
    if typeof(explicit) == "Vector3" then
        return explicit
    end
    local root = rootOf(target)
    if not root then return nil end
    local localCenter = localCenterByTarget[target]
    if typeof(localCenter) ~= "Vector3" then
        local ok, boxCFrame = pcall(function()
            local cf = target:GetBoundingBox()
            return cf
        end)
        if ok and typeof(boxCFrame) == "CFrame" then
            localCenter = root.CFrame:PointToObjectSpace(boxCFrame.Position)
        else
            localCenter = Vector3.new(0, HitEffectConfig.FallbackTargetOffsetY, 0)
        end
        localCenterByTarget[target] = localCenter
    end
    return root.CFrame:PointToWorldSpace(localCenter)
end

function HitEffectService.Publish(attacker: Model, target: Model, critical: boolean, hitPosition: Vector3?)
    if not started or not remote then return end
    local position = targetPosition(target, hitPosition)
    if not position then return end
    local attackerRoot = rootOf(attacker)
    local sourcePosition = if attackerRoot then attackerRoot.Position else position
    local radiusSquared = HitEffectConfig.ServerReplicationRadius * HitEffectConfig.ServerReplicationRadius
    for _, player in Players:GetPlayers() do
        local playerRoot = rootOf(player.Character)
        if playerRoot then
            local delta = playerRoot.Position - position
            if delta:Dot(delta) <= radiusSquared then
                remote:FireClient(player, position, sourcePosition, critical == true)
            end
        end
    end
end

function HitEffectService.Start()
    if started then return end
    started = true
    remote = ensureRemote()
    print(("[game1][HIT_FX] pooled client sparks ready · radius %d"):format(HitEffectConfig.ServerReplicationRadius))
end

return table.freeze(HitEffectService)

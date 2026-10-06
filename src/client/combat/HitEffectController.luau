local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local HitEffectConfig = require(CombatShared:WaitForChild("HitEffectConfig"))
local Effects = script.Parent:WaitForChild("effects")
local HitEffectPool = require(Effects:WaitForChild("HitEffectPool"))

local HitEffectController = {}
local started = false
local pool: any = nil
local tokens = HitEffectConfig.BurstCapacity
local lastRefillAt = os.clock()

local function consumeBurstBudget(): boolean
    local now = os.clock()
    local elapsed = math.max(0, now - lastRefillAt)
    lastRefillAt = now
    tokens = math.min(HitEffectConfig.BurstCapacity, tokens + elapsed * HitEffectConfig.MaxBurstsPerSecond)
    if tokens < 1 then return false end
    tokens -= 1
    return true
end

local function renderCamera(position: Vector3): Camera?
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    local delta = camera.CFrame.Position - position
    if delta:Dot(delta) > HitEffectConfig.ClientRenderRadius * HitEffectConfig.ClientRenderRadius then
        return nil
    end
    return camera
end

local function onHit(position: any, sourcePosition: any, critical: any)
    if typeof(position) ~= "Vector3" then return end
    if typeof(sourcePosition) ~= "Vector3" then sourcePosition = position end
    local camera = renderCamera(position)
    if not camera or not consumeBurstBudget() then return end
    pool:Emit(position, sourcePosition, critical == true, camera.CFrame)
end

function HitEffectController.Start()
    if started then return end
    started = true
    pool = HitEffectPool.new(HitEffectConfig)
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    local remote = remotes:WaitForChild(HitEffectConfig.RemoteName)
    if not remote:IsA("UnreliableRemoteEvent") then
        warn("[game1][HIT_FX] CombatHitEffect has wrong class; hit sparks disabled")
        return
    end
    remote.OnClientEvent:Connect(onHit)
    print(("[game1][HIT_FX] pooled client renderer ready · pool %d"):format(HitEffectConfig.PoolSize))
end

return table.freeze(HitEffectController)

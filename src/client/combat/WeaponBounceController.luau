local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local HitEffectConfig = require(CombatShared:WaitForChild("HitEffectConfig"))
local WeaponBounceConfig = require(CombatShared:WaitForChild("WeaponBounceConfig"))
local WeaponBounceEffectPool = require(script.Parent:WaitForChild("effects"):WaitForChild("WeaponBounceEffectPool"))

local WeaponBounceController = {}
local started = false
local animationController: any = nil
local attackController: any = nil
local effects: any = nil

local function renderCamera(position: Vector3): Camera?
    local camera = Workspace.CurrentCamera
    if not camera then
        return nil
    end
    local radius = math.max(1, tonumber(WeaponBounceConfig.ClientRenderRadius) or 180)
    local delta = camera.CFrame.Position - position
    return if delta:Dot(delta) <= radius * radius then camera else nil
end

local function onBounce(payload: any)
    if type(payload) ~= "table" then
        return
    end

    local clientAttackId = math.floor(tonumber(payload.clientAttackId) or 0)
    local clipId = tostring(payload.clipId or "")
    local attackerUserId = math.floor(tonumber(payload.attackerUserId) or 0)
    if clientAttackId <= 0 or clipId == "" or attackerUserId <= 0 then
        return
    end

    if attackerUserId == Players.LocalPlayer.UserId then
        if attackController and attackController.CancelForBounce then
            attackController.CancelForBounce(clientAttackId)
        end
        if animationController and animationController.BounceCurrentAttack then
            animationController.BounceCurrentAttack(
                clipId,
                tonumber(payload.reverseSpeedMultiplier) or WeaponBounceConfig.ReverseSpeedMultiplier
            )
        end
    end

    local position = payload.position
    local normal = payload.normal
    if effects and typeof(position) == "Vector3" and typeof(normal) == "Vector3" then
        local camera = renderCamera(position)
        if camera then
            if normal.Magnitude <= 1e-5 then
                normal = Vector3.yAxis
            else
                normal = normal.Unit
            end
            effects:Emit(position, normal, camera.CFrame)
        end
    end
end

function WeaponBounceController.Start(animation: any, attack: any)
    animationController = animation
    attackController = attack
    if started then
        return
    end
    started = true

    effects = WeaponBounceEffectPool.new(HitEffectConfig, WeaponBounceConfig.EffectPoolSize)
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    local remote = remotes:WaitForChild(WeaponBounceConfig.RemoteName)
    if not remote:IsA("RemoteEvent") then
        warn("[game1][weapon-bounce] remote has wrong class; bounce presentation disabled")
        return
    end
    remote.OnClientEvent:Connect(onBounce)
end

return table.freeze(WeaponBounceController)

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local WeaponBounceConfig = require(CombatShared:WaitForChild("WeaponBounceConfig"))

local WeaponBounceService = {}
local remote: RemoteEvent? = nil

local function characterPosition(player: Player): Vector3?
    local character = player.Character
    if not character then
        return nil
    end
    local root = character:FindFirstChild("RootCollider")
        or character:FindFirstChild("HumanoidRootPart")
        or character.PrimaryPart
    return if root and root:IsA("BasePart") then root.Position else nil
end

function WeaponBounceService.Start()
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes") or Instance.new("Folder")
    remotes.Name = "Game1Remotes"
    remotes.Parent = ReplicatedStorage

    local existing = remotes:FindFirstChild(WeaponBounceConfig.RemoteName)
    if existing and not existing:IsA("RemoteEvent") then
        existing:Destroy()
        existing = nil
    end
    if not existing then
        existing = Instance.new("RemoteEvent")
        existing.Name = WeaponBounceConfig.RemoteName
        existing.Parent = remotes
    end
    remote = existing :: RemoteEvent
end

function WeaponBounceService.Publish(attacker: Player, payload: any)
    if not remote or type(payload) ~= "table" then
        return
    end

    payload.attackerUserId = attacker.UserId
    local position = payload.position
    local radius = math.max(1, tonumber(WeaponBounceConfig.ServerReplicationRadius) or 160)
    local radiusSquared = radius * radius
    for _, player in ipairs(Players:GetPlayers()) do
        if player == attacker then
            remote:FireClient(player, payload)
        elseif typeof(position) == "Vector3" then
            local viewerPosition = characterPosition(player)
            if viewerPosition then
                local delta = viewerPosition - position
                if delta:Dot(delta) <= radiusSquared then
                    remote:FireClient(player, payload)
                end
            end
        end
    end
end

return table.freeze(WeaponBounceService)

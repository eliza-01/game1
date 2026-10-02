local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Config = require(Shared:WaitForChild("AttackConfig"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))

local Service = {}
local cooldowns = {}

local function modelFromPart(part: Instance): Model?
    local current = part
    while current and current ~= Workspace do
        if current:IsA("Model") and current:GetAttribute("Damageable") == true then
            return current
        end
        current = current.Parent
    end
    return nil
end

local function attack(player: Player, aim: any)
    if typeof(aim) ~= "Vector3" then
        if Config.DebugLogs then
            print(("[game1][ATTACK] REJECT player=%s reason=invalid_aim"):format(player.Name))
        end
        return
    end

    local character = player.Character
    local root = character and character:FindFirstChild("RootCollider")
    if not (character and root and root:IsA("BasePart")) or character:GetAttribute("LifeState") ~= "Alive" then
        if Config.DebugLogs then
            print(("[game1][ATTACK] REJECT player=%s reason=character_not_ready"):format(player.Name))
        end
        return
    end

    local now = os.clock()
    if now - (cooldowns[player] or 0) < Config.CooldownSeconds then
        if Config.DebugLogs then
            print(("[game1][ATTACK] REJECT player=%s reason=cooldown"):format(player.Name))
        end
        return
    end
    cooldowns[player] = now

    local flat = Vector3.new(aim.X - root.Position.X, 0, aim.Z - root.Position.Z)
    if flat.Magnitude < 0.001 then
        flat = root.CFrame.LookVector
    end
    local direction = flat.Unit

    local center = root.Position + direction * (Config.Range * 0.5)
    local boxCf = CFrame.lookAt(center, center + direction)
    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { character }

    local parts = Workspace:GetPartBoundsInBox(
        boxCf,
        Vector3.new(Config.BoxWidth, Config.BoxHeight, Config.Range),
        params
    )

    local seen = {}
    local best, bestDistance = nil, math.huge
    for _, part in ipairs(parts) do
        local model = modelFromPart(part)
        if model and not seen[model] then
            seen[model] = true
            local targetRoot = model:FindFirstChild("RootCollider") or model.PrimaryPart
            if targetRoot and targetRoot:IsA("BasePart") then
                local distance = (targetRoot.Position - root.Position).Magnitude
                if distance <= Config.Range + 1 and distance < bestDistance then
                    best = model
                    bestDistance = distance
                end
            end
        end
    end

    character:SetAttribute("AttackSerial", (character:GetAttribute("AttackSerial") or 0) + 1)

    if not best then
        if Config.DebugLogs then
            print(("[game1][ATTACK] MISS player=%s range=%.1f"):format(player.Name, Config.Range))
        end
        return
    end

    local rawDamage = tonumber(character:GetAttribute("Damage")) or 0
    local finalDamage, killed = DamageService.Apply(character, best, rawDamage)

    if Config.DebugLogs then
        print(("[game1][ATTACK] HIT player=%s target=%s distance=%.2f damage=%d targetHP=%s killed=%s"):format(
            player.Name,
            best.Name,
            bestDistance,
            finalDamage,
            tostring(best:GetAttribute("HP")),
            tostring(killed)
        ))
    end
end

function Service.Start()
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes") or Instance.new("Folder")
    remotes.Name = "Game1Remotes"
    remotes.Parent = ReplicatedStorage

    local event = remotes:FindFirstChild("AttackIntent") or Instance.new("RemoteEvent")
    event.Name = "AttackIntent"
    event.Parent = remotes
    event.OnServerEvent:Connect(attack)

    Players.PlayerRemoving:Connect(function(player)
        cooldowns[player] = nil
    end)
end

return Service

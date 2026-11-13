local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Policy = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("combat"):WaitForChild("AttackFeedbackPolicy"))
local HostilePursuitRegistry = require(script.Parent:WaitForChild("HostilePursuitRegistry"))

local CombatFeedbackService = {}
local started = false
local remote: RemoteEvent? = nil
local lastMeleeFar: {[Player]: number} = setmetatable({}, {__mode = "k"})

local function ensureRemote(): RemoteEvent
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not folder or not folder:IsA("Folder") then
        if folder then folder:Destroy() end
        folder = Instance.new("Folder")
        folder.Name = "Game1Remotes"
        folder.Parent = ReplicatedStorage
    end
    local current = folder:FindFirstChild("CombatFeedback")
    if current and current:IsA("RemoteEvent") then return current end
    if current then current:Destroy() end
    local created = Instance.new("RemoteEvent")
    created.Name = "CombatFeedback"
    created.Parent = folder
    return created
end

local function rootOf(model: Model?): BasePart?
    if not model then return nil end
    local root = model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart") or model.PrimaryPart
    return if root and root:IsA("BasePart") then root else nil
end

function CombatFeedbackService.PublishDamage(attacker: Model?, target: Model, damage: number, critical: boolean, headshot: boolean?)
    if not started or not remote or damage <= 0 then return end
    local root = rootOf(target)
    if not root then return end
    local payload = {
        kind = "damage",
        target = target,
        position = root.Position,
        damage = damage,
        critical = critical == true,
        headshot = headshot == true,
    }
    local sent = {}
    local attackerPlayer = attacker and Players:GetPlayerFromCharacter(attacker) or nil
    if attackerPlayer then
        sent[attackerPlayer] = true
        local outgoing = table.clone(payload)
        outgoing.relation = "outgoing"
        remote:FireClient(attackerPlayer, outgoing)
    end
    local targetPlayer = Players:GetPlayerFromCharacter(target)
    if targetPlayer and not sent[targetPlayer] then
        local incoming = table.clone(payload)
        incoming.relation = "incoming"
        remote:FireClient(targetPlayer, incoming)
    elseif targetPlayer and targetPlayer == attackerPlayer then
        local incoming = table.clone(payload)
        incoming.relation = "incoming"
        remote:FireClient(targetPlayer, incoming)
    end
end

-- All outcome labels share the existing reliable per-player feedback channel.
local function publishLabel(character: Model?, kind: string)
    if not started or not remote or not character then return end
    local player = Players:GetPlayerFromCharacter(character)
    if not player or player.Character ~= character
        or character:GetAttribute("LifeState") ~= "Alive" then return end
    local root = rootOf(character)
    if not root then return end
    remote:FireClient(player, {
        kind = kind,
        target = character,
        position = root.Position,
    })
end

-- The recipient must still be pursued; attacks from NPCs/monsters do not
-- manufacture an out-of-combat Miss after a target was lost.
function CombatFeedbackService.PublishMissOverPlayer(character: Model?)
    if character and HostilePursuitRegistry.IsPursued(character)
        and Policy.AllowIncomingMiss(character:GetAttribute("AttackEndsAt"),
            character:GetAttribute("EquippedWeaponType"), os.clock()) then
        publishLabel(character, "miss")
    end
end

-- Called only after a completed player attack that dealt no damage.
-- No target + no pursuer is silent. Far has priority over Miss, with a
-- per-player throttle for melee; bow shots report Far at every Release.
function CombatFeedbackService.PublishAttackOutcome(character: Model, aimedState: string?, isBow: boolean)
    local player = Players:GetPlayerFromCharacter(character)
    if not player then return end
    local kind = Policy.Resolve(HostilePursuitRegistry.IsPursued(character), aimedState, isBow)
    if kind == "far" and not isBow then
        local now = os.clock()
        if not Policy.CanShowMeleeFar(lastMeleeFar[player], now) then return end
        lastMeleeFar[player] = now
    end
    if kind then publishLabel(character, kind) end
end

function CombatFeedbackService.Start()
    if started then return end
    started = true
    remote = ensureRemote()
    Players.PlayerRemoving:Connect(function(player)
        lastMeleeFar[player] = nil
    end)
    print("[game1][COMBAT_FEEDBACK] reliable damage numbers ready")
end

return table.freeze(CombatFeedbackService)

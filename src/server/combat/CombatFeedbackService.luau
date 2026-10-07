local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local CombatFeedbackService = {}
local started = false
local remote: RemoteEvent? = nil

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

function CombatFeedbackService.PublishDamage(attacker: Model?, target: Model, damage: number, critical: boolean)
    if not started or not remote or damage <= 0 then return end
    local root = rootOf(target)
    if not root then return end
    local payload = {
        kind = "damage",
        target = target,
        position = root.Position,
        damage = damage,
        critical = critical == true,
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

function CombatFeedbackService.Start()
    if started then return end
    started = true
    remote = ensureRemote()
    print("[game1][COMBAT_FEEDBACK] reliable damage numbers ready")
end

return table.freeze(CombatFeedbackService)

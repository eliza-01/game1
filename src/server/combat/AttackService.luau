local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local Config = require(CombatShared:WaitForChild("AttackConfig"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local CharacterAnimationRegistry = require(CharacterShared:WaitForChild("CharacterAnimationRegistry"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))
local HitEffectService = require(script.Parent:WaitForChild("HitEffectService"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))

local AttackService = {}
local activeUntil: { [Player]: number } = {}
local activeSerial: { [Player]: number } = {}

local function modelFromPart(part: Instance): Model?
    local current: Instance? = part
    while current and current ~= Workspace do
        if current:IsA("Model") and current:GetAttribute("Damageable") == true then
            return current
        end
        current = current.Parent
    end
    return nil
end

local function rowsForEquippedAttack(character: Model): any
    local profileId = tostring(character:GetAttribute("AnimationProfileId") or character:GetAttribute("CharacterArchetype") or "")
    local profile = CharacterAnimationRegistry.profiles[profileId]
    if not profile then
        return nil
    end

    local weaponSet = tostring(character:GetAttribute("AnimationWeaponSet") or "")
    if weaponSet ~= "" and weaponSet ~= "base" and weaponSet ~= "unarmed" then
        local weapon = profile.weapons and profile.weapons[weaponSet]
        if weapon and weapon.attack then
            return weapon.attack
        end
    end
    return profile.base and profile.base.attack or nil
end

local function isAllowedAttackClip(character: Model, clipId: string): boolean
    if clipId == "" then
        return false
    end
    for _, descriptor in ipairs(rowsForEquippedAttack(character) or {}) do
        if tostring(descriptor.clipId or "") == clipId then
            return true
        end
    end
    return false
end

local function resolveMeleeDamage(player: Player, character: Model, serial: number, aim: Vector3)
    if activeSerial[player] ~= serial
        or player.Character ~= character
        or not character.Parent
        or tostring(character:GetAttribute("LifeState") or "") ~= "Alive"
    then
        return
    end

    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then
        return
    end

    local flat = Vector3.new(aim.X - root.Position.X, 0, aim.Z - root.Position.Z)
    if flat.Magnitude < 0.001 then
        flat = root.CFrame.LookVector
    end
    local direction = flat.Unit
    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local center = root.Position + direction * (attackRange * 0.5)
    local boxCf = CFrame.lookAt(center, center + direction)

    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { character }

    local parts = Workspace:GetPartBoundsInBox(
        boxCf,
        Vector3.new(Config.BoxWidth, Config.BoxHeight, attackRange),
        params
    )

    local seen = {}
    local best: Model? = nil
    local bestZone = "root"
    local bestHitPosition: Vector3? = nil
    local bestDistance = math.huge
    local attackBoxSize = Vector3.new(Config.BoxWidth, Config.BoxHeight, attackRange)
    for _, part in parts do
        local model = modelFromPart(part)
        if model and not seen[model] then
            seen[model] = true
            local targetRoot = model:FindFirstChild("RootCollider") or model.PrimaryPart
            if targetRoot and targetRoot:IsA("BasePart") then
                local distance = (targetRoot.Position - root.Position).Magnitude
                local virtualHit = EntityHitboxService.QueryBox(model, boxCf, attackBoxSize)
                local hasVirtualRig = EntityHitboxService.HasBinding(model)
                local intersectsTarget = if hasVirtualRig then virtualHit ~= nil else true
                if intersectsTarget and distance <= attackRange + 1 and distance < bestDistance then
                    best = model
                    bestZone = tostring(virtualHit and virtualHit.hitZone or "root")
                    bestHitPosition = if virtualHit and typeof(virtualHit.hitPosition) == "Vector3"
                        then virtualHit.hitPosition
                        else targetRoot.Position
                    bestDistance = distance
                end
            end
        end
    end

    if not best then
        if Config.DebugLogs then
            print(("[game1][attack] miss player=%s range=%.1f serial=%d"):format(player.Name, attackRange, serial))
        end
        return
    end

    local rawDamage = tonumber(character:GetAttribute("Damage")) or 0
    local finalDamage, killed = DamageService.Apply(character, best, rawDamage)
    HitEffectService.Publish(character, best, best:GetAttribute("LastCritical") == true, bestHitPosition)
    if Config.DebugLogs then
        print(("[game1][attack] hit player=%s target=%s zone=%s distance=%.2f damage=%d targethp=%s killed=%s serial=%d")
            :format(
                player.Name,
                best.Name,
                bestZone,
                bestDistance,
                finalDamage,
                tostring(best:GetAttribute("HP")),
                tostring(killed),
                serial
            ))
    end
end

local function scheduleTimelineResults(player: Player, character: Model, serial: number, aim: Vector3, timing: any)
    for eventName, event in pairs(timing.events or {}) do
        local resultType = tostring(event.result or "")
        local delaySeconds = math.max(0, tonumber(event.time) or 0)
        if resultType == AttackTimelineConfig.ResultTypes.MeleeDamage then
            task.delay(delaySeconds, function()
                resolveMeleeDamage(player, character, serial, aim)
            end)
        elseif Config.DebugLogs and resultType ~= "" then
            warn(("[game1][attack] no result handler event=%s result=%s"):format(tostring(eventName), resultType))
        end
    end
end

local function clearAttackStateLater(player: Player, character: Model, serial: number, durationSeconds: number)
    task.delay(durationSeconds, function()
        if activeSerial[player] ~= serial then
            return
        end
        activeUntil[player] = nil
        activeSerial[player] = nil
        if character.Parent and tonumber(character:GetAttribute("AttackSerial")) == serial then
            character:SetAttribute("AttackEndsAt", nil)
            character:SetAttribute("AttackClipId", nil)
        end
    end)
end

local function attack(player: Player, payload: any)
    if type(payload) ~= "table" or typeof(payload.aim) ~= "Vector3" then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=invalid_payload"):format(player.Name))
        end
        return
    end

    local aim: Vector3 = payload.aim
    local clipId = tostring(payload.clipId or "")
    local character = player.Character
    local root = character and character:FindFirstChild("RootCollider")
    if not (character and root and root:IsA("BasePart")) or character:GetAttribute("LifeState") ~= "Alive" then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=character_not_ready"):format(player.Name))
        end
        return
    end

    if not isAllowedAttackClip(character, clipId) then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=invalid_clip clip=%s"):format(player.Name, clipId))
        end
        return
    end

    local attackSpeed = math.max(1, tonumber(character:GetAttribute("AttackSpeed")) or AttackTimelineConfig.DefaultAttackSpeed)
    local timing = AttackTimelineConfig.ResolveRuntime(clipId, attackSpeed)
    if not timing then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_timeline clip=%s"):format(player.Name, clipId))
        end
        return
    end

    local now = os.clock()
    if now < (activeUntil[player] or 0) then
        return
    end

    local attackDuration = timing.duration
    local serial = (tonumber(character:GetAttribute("AttackSerial")) or 0) + 1
    activeSerial[player] = serial
    activeUntil[player] = now + attackDuration
    character:SetAttribute("AttackSerial", serial)
    character:SetAttribute("AttackClipId", clipId)
    character:SetAttribute("AttackStartedAt", now)
    character:SetAttribute("AttackEndsAt", now + attackDuration)

    -- Gameplay results are not resolved on input. They are scheduled from the
    -- same clip timeline that owns the animation lock, so damage/release windows
    -- stay attached to authored animation periods when AttackSpeed changes.
    scheduleTimelineResults(player, character, serial, aim, timing)
    clearAttackStateLater(player, character, serial, attackDuration)
end

function AttackService.Start()
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes") or Instance.new("Folder")
    remotes.Name = "Game1Remotes"
    remotes.Parent = ReplicatedStorage

    local event = remotes:FindFirstChild("AttackIntent") or Instance.new("RemoteEvent")
    event.Name = "AttackIntent"
    event.Parent = remotes
    event.OnServerEvent:Connect(attack)

    Players.PlayerRemoving:Connect(function(player)
        activeUntil[player] = nil
        activeSerial[player] = nil
    end)
end

return table.freeze(AttackService)

-- Server-owned flying-arrow simulation. The camera ray is an aim *request*,
-- never a client hit report. One projectile, one first contact, one damage event.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Debris = game:GetService("Debris")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat")
local Policy = require(Shared:WaitForChild("BowProjectileConfig"))
local Geometry = require(Shared:WaitForChild("BowAimGeometry"))
local AttackConfig = require(Shared:WaitForChild("AttackConfig"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))
local HitEffectService = require(script.Parent:WaitForChild("HitEffectService"))
local ArrowVisualFactory = require(script.Parent:WaitForChild("ArrowVisualFactory"))
local ArrowImpactAttachment = require(script.Parent:WaitForChild("ArrowImpactAttachment"))

-- A decorative reaction must not prevent the authoritative combat module from starting.
local swayOk, swayModule = pcall(function()
    return require(script.Parent.Parent:WaitForChild("world"):WaitForChild("LandscapeSwayService"))
end)
local LandscapeSwayService = if swayOk then swayModule else nil

local BowProjectileService = {}
local active = {}
local started = false
local folder: Folder? = nil

local function projectileFolder(): Folder
    if folder and folder.Parent then return folder end
    local existing = Workspace:FindFirstChild("Game1Projectiles")
    if existing and existing:IsA("Folder") then
        folder = existing
    else
        folder = Instance.new("Folder")
        folder.Name = "Game1Projectiles"
        folder.Parent = Workspace
    end
    return folder :: Folder
end

local function worldRayParams(character: Model): RaycastParams
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = {character, projectileFolder()}
    params.IgnoreWater = false
    params.RespectCanCollide = false
    return params
end

local function arrowFrame(position: Vector3, direction: Vector3): CFrame
    local up = if math.abs(direction.Unit:Dot(Vector3.yAxis)) > 0.98
        then Vector3.zAxis else Vector3.yAxis
    return CFrame.lookAt(position, position + direction, up)
end

local function muzzlePosition(root: BasePart): Vector3
    -- Bone.Transform is not network-replicated. The authoritative spawn is
    -- derived from the server-visible root, NEVER an untrusted client nock.
    return root.Position + root.CFrame.LookVector * Policy.MinSpawnDistance + Vector3.yAxis * 1.3
end

local function damageableAncestor(part: Instance?, shooter: Model): Model?
    local cursor = part
    while cursor and cursor ~= Workspace do
        if cursor:IsA("Model") and cursor ~= shooter and cursor:GetAttribute("Damageable") == true then
            return cursor
        end
        cursor = cursor.Parent
    end
    return nil
end

-- RootCollider is a movement proxy, not visible mesh. Arrow precision is
-- decided by EntityHitboxService; otherwise a large invisible collider causes
-- body hits in empty space, especially beside an actor's head.
local function worldContact(character: Model, origin: Vector3, displacement: Vector3): RaycastResult?
    local params = worldRayParams(character)
    local excluded = params.FilterDescendantsInstances
    for _ = 1, 12 do
        local hit = Workspace:Raycast(origin, displacement, params)
        if not hit then return nil end
        if hit.Instance.Name ~= "RootCollider" or not damageableAncestor(hit.Instance, character) then
            return hit
        end
        table.insert(excluded, hit.Instance)
        params.FilterDescendantsInstances = excluded
    end
    return nil
end

local function discard(index: number)
    local state = active[index]
    if not state then return end
    if state.visual then state.visual:Destroy() end
    table.remove(active, index)
end

-- Leave a short-lived cosmetic arrow at the impact point. Once a projectile
-- contacts the world, no more damage or raycasts occur for that projectile.
local function settle(index: number, contact: Vector3, direction: Vector3, hitInstance: Instance?, entity: Model?, boneName: string?)
    local state = active[index]
    if not state then return end
    local visual = state.visual
    if visual then
        -- The nose of a -Z-authored arrow sits ahead of its pivot. Avoid
        -- burying the entire shaft inside geometry.
        local frame = ArrowVisualFactory.ContactFrame(visual, contact, direction,
            state.penetrationStuds)
        ArrowVisualFactory.Place(visual, frame, state.visualCorrection)
        -- Stuck arrows follow an animated Bone on actors or use a native weld
        -- for rigid props. World-only impacts remain anchored at contact.
        ArrowImpactAttachment.Attach(visual, hitInstance, entity, boneName)
        Debris:AddItem(visual, 2.5)
        state.visual = nil
    end
    discard(index)
end

local function impact(state: any, hit: any, point: Vector3)
    if not hit or not hit.model or not hit.model.Parent then return end
    local target: Model = hit.model
    if target == state.character or target:GetAttribute("Damageable") ~= true then return end
    local headshot = hit.zone == "head"
    local baseDamage = math.max(0, tonumber(state.damage) or 0)
    local amount = baseDamage * (if headshot then AttackConfig.HeadshotDamageMultiplier else 1)
    DamageService.Apply(state.character, target, amount, headshot)
    target:SetAttribute("LastHitZone", if headshot then "head" else "body")
    target:SetAttribute("LastHeadshot", headshot)
    HitEffectService.Publish(state.character, target, target:GetAttribute("LastCritical") == true, point)
end

local function step(dt: number)
    local delta = math.clamp(dt, 0, 0.1) -- swept ray covers the full step, even below 30 FPS
    for i = #active, 1, -1 do
        local state = active[i]
        if not state.character.Parent
            or not state.player.Parent
            or state.player.Character ~= state.character
            or state.character:GetAttribute("LifeState") ~= "Alive"
            or os.clock() - state.born >= Policy.MaxLifetime
            or state.distance >= state.maxDistance
        then
            discard(i)
        else
            local startPosition = state.position
            local nextVelocity = state.velocity - Vector3.yAxis * Policy.Gravity * delta
            local nextPosition = startPosition + (state.velocity + nextVelocity) * (0.5 * delta)
            local displacement = nextPosition - startPosition
            local remaining = math.max(0, state.maxDistance - state.distance)
            if displacement.Magnitude > remaining then
                displacement = displacement.Unit * remaining
            end
            local distance = displacement.Magnitude
            if distance < 1e-6 then
                discard(i)
            else
                local direction = displacement / distance
                local worldHit = worldContact(state.character, startPosition, displacement)
                local entityHit = EntityHitboxService.RaycastAimRegions(state.character, startPosition, direction, distance, true)
                local blockedAt = worldHit and worldHit.Distance or distance
                local sameTarget = worldHit and damageableAncestor(worldHit.Instance, state.character) or nil
                local eligibleHit = entityHit and (entityHit.distance <= blockedAt + 0.08
                    or (sameTarget and sameTarget == entityHit.model))
                if eligibleHit then
                    if worldHit and worldHit.Distance <= entityHit.distance + 0.08 and LandscapeSwayService then
                        LandscapeSwayService.Impact(worldHit.Instance, worldHit.Position, state.velocity)
                    end
                    impact(state, entityHit, entityHit.hitPosition)
                    settle(i, entityHit.hitPosition, direction,
                        if sameTarget and sameTarget == entityHit.model then worldHit.Instance else nil,
                        entityHit.model, entityHit.boneName)
                elseif worldHit then
                    if LandscapeSwayService then
                        LandscapeSwayService.Impact(worldHit.Instance, worldHit.Position, state.velocity)
                    end
                    if sameTarget then
                        impact(state, {model = sameTarget, zone = "body"}, worldHit.Position)
                    end
                    settle(i, worldHit.Position, direction, worldHit.Instance, sameTarget, nil)
                else
                    state.position = startPosition + displacement
                    state.velocity = nextVelocity
                    state.distance += distance
                    ArrowVisualFactory.Place(state.visual, arrowFrame(state.position, nextVelocity), state.visualCorrection)
                end
            end
        end
    end
end

-- Caller has already validated the equipped bow, registered clip, cadence and
-- timeline. A player may not nominate arbitrary damage or an arbitrary spawn.
function BowProjectileService.Release(player: Player, character: Model, cameraOrigin: Vector3, cameraDirection: Vector3): boolean
    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") or player.Character ~= character
        or character:GetAttribute("LifeState") ~= "Alive"
        or string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) ~= "bow" then
        return false
    end
    local origin, direction = Geometry.Validate(root, cameraOrigin, cameraDirection)
    if not origin or not direction then return false end
    local count = 0
    for _, state in ipairs(active) do
        if state.player == player then count += 1 end
    end
    if count >= Policy.MaxActivePerPlayer then return false end

    -- The bow's Range is authoritative; global MaxDistance is only a safety cap.
    -- Melee AttackRadius is a different mechanic and remains unchanged.
    local bowRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Policy.MaxDistance,
        1, Policy.MaxDistance)
    local aimHit = worldContact(character, origin, direction * bowRange)
    local aimPoint = if aimHit then aimHit.Position else origin + direction * bowRange
    local spawnPosition = muzzlePosition(root)
    if (spawnPosition - root.Position).Magnitude > 12 then return false end
    local arrowSlug, arrowDefinition, flightSpeed = ArrowVisualFactory.ActiveDefinition()
    local shotDirection = Geometry.BallisticDirection(spawnPosition, aimPoint, flightSpeed, Policy.Gravity)
    if not shotDirection then return false end
    -- Visible FBX arrow is an anchored, replicated world Model. Swept server
    -- raycasts remain authoritative, so a thin arrow cannot tunnel through targets.
    local visual, visualCorrection = ArrowVisualFactory.Create(
        arrowDefinition, arrowSlug, arrowFrame(spawnPosition, shotDirection), projectileFolder())
    table.insert(active, {
        player = player,
        character = character,
        damage = tonumber(character:GetAttribute("Damage")) or 0,
        position = spawnPosition,
        velocity = shotDirection * flightSpeed,
        visualCorrection = visualCorrection,
        penetrationStuds = if arrowDefinition then arrowDefinition.penetrationStuds else 0.12,
        born = os.clock(),
        distance = 0,
        maxDistance = math.max(0, bowRange - (spawnPosition - root.Position).Magnitude),
        visual = visual,
    })
    return true
end

function BowProjectileService.Start()
    if started then return end
    started = true
    RunService.Heartbeat:Connect(step)
    Players.PlayerRemoving:Connect(function(player)
        for i = #active, 1, -1 do
            if active[i].player == player then discard(i) end
        end
    end)
end

return table.freeze(BowProjectileService)

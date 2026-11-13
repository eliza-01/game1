-- Server-authoritative instant bow contact. One final camera sample, one Release,
-- one validated hit record. Flying and embedded arrows are purely client visuals.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local Policy = require(CombatShared:WaitForChild("BowProjectileConfig"))
local Geometry = require(CombatShared:WaitForChild("BowAimGeometry"))
local Range = require(CombatShared:WaitForChild("BowRangeGeometry"))
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local Factory = require(CombatShared:WaitForChild("ArrowVisualFactory"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))
local HitEffectService = require(script.Parent:WaitForChild("HitEffectService"))
local Surface = require(script.Parent:WaitForChild("ArrowSurfaceContact"))

local swayOk, swayModule = pcall(function()
    return require(script.Parent.Parent:WaitForChild("world"):WaitForChild("LandscapeSwayService"))
end)
local LandscapeSwayService = if swayOk then swayModule else nil

local Service = {}
local remote: RemoteEvent? = nil
local started = false
local shotSerial = 0

local function rayParams(character: Model): RaycastParams
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = {character}
    params.RespectCanCollide = false
    params.IgnoreWater = false
    return params
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

-- Ignore movement proxies and the overlarge Landscape Painter aim proxy.
-- The latter is resolved once against its actual mesh; no pivot/box fallback.
local function worldContact(character: Model, origin: Vector3, displacement: Vector3): any?
    if displacement.Magnitude <= 1e-6 then return nil end
    local params = rayParams(character)
    local excluded = params.FilterDescendantsInstances
    local proxyContact = nil
    for _ = 1, 12 do
        local hit = Workspace:Raycast(origin, displacement, params)
        if not hit then return proxyContact end
        if hit.Instance.Name == "LandscapeSwayTarget"
            and hit.Instance:GetAttribute("Game1LandscapeSwayTarget") == true then
            local surface = Surface.Resolve(hit.Instance, origin, displacement)
            if surface and (not proxyContact or surface.Distance < proxyContact.Distance) then
                proxyContact = surface
            end
            table.insert(excluded, hit.Instance)
        elseif hit.Instance.Name == "RootCollider" and damageableAncestor(hit.Instance, character) then
            table.insert(excluded, hit.Instance)
        else
            return if proxyContact and proxyContact.Distance <= hit.Distance then proxyContact else hit
        end
        params.FilterDescendantsInstances = excluded
    end
    return proxyContact
end

local function safeLocalContact(part: BasePart?, position: Vector3?): Vector3?
    if not part or not part.Parent or typeof(position) ~= "Vector3" then return nil end
    return part.CFrame:PointToObjectSpace(position)
end

-- This immutable-style record contains NO arrow Instance and does not move or
-- follow the enemy. Hitbox = gameplay; COL/MeshPart = optional cosmetic contact.
function Service.Capture(character: Model, cameraOrigin: Vector3,
    cameraDirection: Vector3, launchCandidate: any): any?
    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then return nil end
    local origin, direction = Geometry.Validate(root, cameraOrigin, cameraDirection)
    if not origin or not direction then return nil end
    local range = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Policy.MaxDistance,
        1, Policy.MaxDistance)
    -- Camera and nock can be behind the character: neither offset consumes the
    -- advertised AttackRadius. Cast far enough to find a surface, then gate
    -- gameplay contact against the authoritative character-centered radius.
    local castDistance = Range.CastDistance(root.Position, origin, range, Policy.MaxDistance)
    local world = worldContact(character, origin, direction * castDistance)
    local actor = EntityHitboxService.RaycastAimRegions(character, origin, direction, castDistance, true)
    if actor and not Range.Within(root.Position, actor.hitPosition, range) then actor = nil end
    -- Keep out-of-range walls for line-of-sight blocking. They must not
    -- become ranged contacts, but must still block targets behind them.
    local worldWithinRange = world ~= nil and Range.Within(root.Position, world.Position, range)
    local blocked = if world then world.Distance else castDistance
    local sameActor = if world then damageableAncestor(world.Instance, character) else nil
    if actor and actor.distance > blocked + Policy.OcclusionTolerance and sameActor ~= actor.model then
        actor = nil
    end

    local point = if actor then actor.hitPosition elseif worldWithinRange then world.Position else origin + direction * range
    local surface = nil
    if actor then
        -- One geometry refinement at capture time; never cast to target geometry
        -- during the visual flight. If no believable surface exists, no stuck arrow.
        surface = Surface.ResolveEntity(actor.model, origin, direction,
            actor.distance, math.min(castDistance, actor.distance + Policy.VisualSurfaceSearchAhead))
    elseif worldWithinRange then
        surface = world
    end
    local part = surface and surface.Instance or nil
    local localContact = if part and part:IsA("BasePart") then safeLocalContact(part, surface.Position) else nil
    -- Preserve the impacted hitbox bone, not the nearest bone chosen AFTER
    -- Death moved the skeleton. This avoids head arrows reattaching to legs.
    local impactBone = nil
    local boneLocal = nil
    if actor and part and localContact and type(actor.boneName) == "string"
        and actor.boneName ~= "" then
        local visual = actor.model:FindFirstChild("Visual") or actor.model:FindFirstChild("ImportedRig") or actor.model
        local found = visual:FindFirstChild(actor.boneName, true)
        if found and found:IsA("Bone") then
            impactBone = found
            boneLocal = found.TransformedWorldCFrame:PointToObjectSpace(surface.Position)
        end
    end
    local launch = Geometry.ValidateLaunch(root, launchCandidate)
    if RunService:IsStudio() and AttackConfig.DebugLogs then
        print(("[game1][bow] hitscan_capture target=%s zone=%s surface=%s")
            :format(if actor then actor.model.Name elseif world then "world" else "none",
                if actor then actor.zone else "none", part and part.Name or "none"))
    end
    return {
        point = point,
        target = if actor then actor.model else nil,
        zone = if actor then actor.zone else nil,
        contactPart = part,
        contactLocal = localContact,
        contactBone = impactBone,
        contactBoneLocal = boneLocal,
        -- For a World hit, the camera chooses an actual collision surface.
        worldHit = worldWithinRange and actor == nil,
        launchLocal = if launch then root.CFrame:PointToObjectSpace(launch) else nil,
    }
end

local function releaseOrigin(character: Model, root: BasePart, localPoint: any): Vector3
    local candidate = if typeof(localPoint) == "Vector3"
        then Geometry.ValidateLaunch(root, root.CFrame:PointToWorldSpace(localPoint)) else nil
    if candidate then
        local weapon = character:FindFirstChild("EquippedWeapon")
        local name = weapon and tostring(weapon:GetAttribute("WeaponTargetBoneName") or "") or ""
        local visual = character:FindFirstChild("Visual") or character
        local bone = if name ~= "" then visual:FindFirstChild(name, true) else nil
        if bone and bone:IsA("Bone") and
            (candidate - bone.TransformedWorldCFrame.Position).Magnitude > Policy.MaxLaunchSocketError then
            candidate = nil
        end
        if candidate then
            local safeStart = root.Position + Vector3.yAxis * 1.3
            if (candidate - safeStart).Magnitude > 0.01
                and worldContact(character, safeStart, candidate - safeStart) then
                candidate = nil
            end
        end
    end
    return candidate or root.Position + root.CFrame.LookVector * Policy.MinSpawnDistance + Vector3.yAxis * 1.3
end

local function canReach(character: Model, from: Vector3, point: Vector3, target: Model?,
    expectedPart: BasePart?): (boolean, any?)
    local delta = point - from
    if delta.Magnitude < 0.01 then return false, nil end
    local blocking = worldContact(character, from, delta)
    if not blocking or blocking.Distance >= delta.Magnitude - Policy.OcclusionTolerance then
        return true, nil
    end
    if target and damageableAncestor(blocking.Instance, character) == target then
        return true, nil
    end
    -- The same static surface may be seen from a different offset by the bow.
    if expectedPart and blocking.Instance == expectedPart and not target then
        return true, nil
    end
    return false, blocking
end

local function publish(payload: any)
    if not remote then return end
    local center = payload.origin
    local finish = payload.point
    local rangeSquared = Policy.VisualReplicationRadius * Policy.VisualReplicationRadius
    for _, player in ipairs(Players:GetPlayers()) do
        local character = player.Character
        local root = character and (character:FindFirstChild("RootCollider") or character:FindFirstChild("NavigationRoot"))
        if root and root:IsA("BasePart") then
            local d0 = (root.Position - center).Magnitude
            local d1 = (root.Position - finish).Magnitude
            if math.min(d0 * d0, d1 * d1) <= rangeSquared then
                remote:FireClient(player, payload)
            end
        end
    end
end

-- Server applies damage immediately at the authored Release; the visual arrow
-- subsequently flies toward the FROZEN point with no collision polling.
function Service.Release(player: Player, character: Model, snapshot: any): (boolean, number)
    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") or player.Character ~= character
        or character:GetAttribute("LifeState") ~= "Alive"
        or string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) ~= "bow"
        or type(snapshot) ~= "table" or typeof(snapshot.point) ~= "Vector3" then
        return false
    end
    local from = releaseOrigin(character, root, snapshot.launchLocal)
    local delta = snapshot.point - from
    if delta.Magnitude <= 0.01 then return false end
    local bowRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Policy.MaxDistance,
        1, Policy.MaxDistance)
    local withinRange = Range.Within(root.Position, snapshot.point, bowRange)
    local endPoint = from + delta.Unit * math.min(delta.Magnitude, bowRange)
    if withinRange then endPoint = snapshot.point end
    local target: Model? = if withinRange and snapshot.target and snapshot.target.Parent
        and snapshot.target:GetAttribute("Damageable") == true
        and snapshot.target:GetAttribute("LifeState") == "Alive"
        then snapshot.target else nil
    local allowed, blocker = canReach(character, from, endPoint, target,
        if snapshot.contactPart and snapshot.contactPart:IsA("BasePart") then snapshot.contactPart else nil)
    if not allowed and blocker then
        endPoint = blocker.Position
        target = nil
    end
    if not withinRange then target = nil end

    local hitPart: BasePart? = if allowed and withinRange and snapshot.contactPart
        and snapshot.contactPart:IsA("BasePart") and snapshot.contactPart.Parent
        then snapshot.contactPart else nil
    local localPoint = if hitPart then snapshot.contactLocal else nil
    if target and (not hitPart or not hitPart:IsDescendantOf(target)) then
        -- Head/body damage still occurs; never fake an arrow on the hitbox.
        hitPart = nil
        localPoint = nil
    end
    if not target and not snapshot.worldHit then
        hitPart = nil
        localPoint = nil
    end
    if not allowed and blocker then
        hitPart = if blocker.Instance:IsA("BasePart") then blocker.Instance else nil
        localPoint = if hitPart then safeLocalContact(hitPart, blocker.Position) else nil
    end

    local slug, arrowRow, speed = Factory.ActiveDefinition()
    shotSerial += 1
    local flightSeconds = math.max(0.02, (endPoint - from).Magnitude / speed)
    local payload = {
        schemaVersion = 1,
        shotId = shotSerial,
        origin = from,
        point = endPoint,
        launchedAt = Workspace:GetServerTimeNow(),
        duration = flightSeconds,
        arrowSlug = slug,
        penetrationStuds = if arrowRow then arrowRow.penetrationStuds else 0.12,
        hitPart = hitPart,
        hitLocal = localPoint,
        hitBone = if target then snapshot.contactBone else nil,
        hitBoneLocal = if target then snapshot.contactBoneLocal else nil,
        target = target,
        zone = if target then snapshot.zone else nil,
    }
    -- Send visual coordinates BEFORE damage can initiate Death/rig cleanup.
    publish(payload)
    local damageDealt = 0
    if target then
        local headshot = snapshot.zone == "head"
        local damage = math.max(0, tonumber(character:GetAttribute("Damage")) or 0)
        damageDealt = DamageService.Apply(character, target,
            damage * (if headshot then AttackConfig.HeadshotDamageMultiplier else 1), headshot)
        target:SetAttribute("LastHitZone", if headshot then "head" else "body")
        target:SetAttribute("LastHeadshot", headshot)
        HitEffectService.Publish(character, target, target:GetAttribute("LastCritical") == true, snapshot.point)
    elseif hitPart and LandscapeSwayService then
        task.delay(flightSeconds, function()
            if hitPart and hitPart.Parent then
                LandscapeSwayService.Impact(hitPart, endPoint, delta.Unit)
            end
        end)
    end
    if RunService:IsStudio() and AttackConfig.DebugLogs then
        print(("[game1][bow] hitscan_release id=%d result=%s zone=%s visual=%s")
            :format(shotSerial, if target then target.Name else "world", tostring(payload.zone),
                if hitPart then hitPart.Name else "no-embedded-arrow"))
    end
    return true, damageDealt
end

function Service.Start()
    if started then return end
    started = true
    Factory.PublishActiveTemplate()
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Game1Remotes"
        folder.Parent = ReplicatedStorage
    end
    local existing = folder:FindFirstChild("BowShotVisual")
    if existing and not existing:IsA("RemoteEvent") then error("BowShotVisual must be RemoteEvent") end
    remote = existing or Instance.new("RemoteEvent")
    remote.Name = "BowShotVisual"
    remote.Parent = folder
end

return table.freeze(Service)

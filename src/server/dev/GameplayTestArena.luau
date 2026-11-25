--!strict
-- Geometry and temporary population; production rig/hitbox/AI pipeline remains authoritative.
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local CharacterConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local AttackConfig = require(Shared:WaitForChild("combat"):WaitForChild("AttackConfig"))
local Spawner = require(script.Parent.Parent:WaitForChild("monster"):WaitForChild("MonsterSpawnerService"))
local Weapons = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))
local Appearance = require(script.Parent:WaitForChild("GameplayTestAppearance"))
local Arena = {}
local serial = 0

function Arena.Spacing(size: Vector3): number
    local reach = AttackConfig.Range
    for _, row in ipairs(Balance.Weapons) do
        if row.type ~= "bow" then reach = math.max(reach, row.radius) end
    end
    -- A disk of attack reach + a conservative full model diagonal cannot overlap its neighbour.
    return math.ceil(2 * (reach + size.Magnitude) + 4)
end
function Arena.Surface(point: Vector3, character: Model?): (Vector3, boolean)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    local excluded = {}
    local monsters = Workspace:FindFirstChild("Monsters")
    if monsters then table.insert(excluded, monsters) end
    if character then table.insert(excluded, character) end
    params.FilterDescendantsInstances = excluded
    params.RespectCanCollide = true
    local hit = Workspace:Raycast(point + Vector3.new(0, 6, 0), Vector3.new(0, -18, 0), params)
    return if hit then hit.Position else point, hit ~= nil
end
function Arena.Support(parent: Instance, point: Vector3, width: number)
    local pad = Instance.new("Part")
    pad.Name = "TestSupport"
    pad.Size = Vector3.new(width, 1, width)
    pad.Position = point - Vector3.new(0, 0.5, 0)
    pad.Anchored = true; pad.Material = Enum.Material.SmoothPlastic
    pad.Color = Color3.fromRGB(65, 73, 78)
    pad.Parent = parent
end
-- A single continuous deck, tiled only if a Part would exceed the engine size limit.
local function deck(parent: Instance, name: string, top: CFrame, width: number, depth: number, color: Color3)
    local folder = Instance.new("Folder")
    folder.Name = name
    folder.Parent = parent
    local count = math.max(1, math.ceil(width / 1024))
    local segment = width / count
    for index = 1, count do
        local part = Instance.new("Part")
        part.Name = name .. "_" .. index
        part.Size = Vector3.new(segment, 1, depth)
        part.CFrame = top * CFrame.new(-width / 2 + (index - 0.5) * segment, -0.5, 0)
        part.Anchored = true
        part.Material = Enum.Material.SmoothPlastic
        part.Color = color
        part.TopSurface = Enum.SurfaceType.Smooth
        part.BottomSurface = Enum.SurfaceType.Smooth
        part.Parent = folder
    end
    return folder
end

function Arena.BuildLinePlatform(parent: Instance, origin: CFrame, count: number, spacing: number, size: Vector3): (CFrame, Vector3)
    local groupMargin = math.max(12, math.ceil(Balance.Test.maxGroup * (math.max(size.X, size.Z) + 2) / (2 * math.pi)) + 4)
    local width = (count - 1) * spacing + 2 * groupMargin
    local centerX = (count - 1) * spacing / 2
    local backEdge = -24 - math.max(8, size.Z / 2 + 4)
    local frontEdge = groupMargin
    local floorY = -CharacterConfig.RootAnchorOffset
    local platformTop = origin * CFrame.new(centerX, floorY, (backEdge + frontEdge) / 2)
    deck(parent, "MonsterPlatform", platformTop, width, frontEdge - backEdge, Color3.fromRGB(65, 73, 78))
    local trackWidth = 12
    local trackTop = origin * CFrame.new(centerX, floorY, backEdge - trackWidth / 2)
    deck(parent, "SprintTrack", trackTop, width, trackWidth, Color3.fromRGB(45, 115, 98))
    return trackTop, Vector3.new(width, 0, trackWidth)
end

function Arena.IsOnTrack(trackTop: CFrame, trackSize: Vector3, rootPosition: Vector3): boolean
    local feet = rootPosition - Vector3.new(0, CharacterConfig.RootAnchorOffset, 0)
    local point = trackTop:PointToObjectSpace(feet)
    return math.abs(point.X) <= trackSize.X / 2
        and math.abs(point.Z) <= trackSize.Z / 2 and point.Y >= -0.75 and point.Y <= 4
end

function Arena.ShowWeapons(parent: Instance, origin: CFrame, character: Model)
    local types = {sword=0, dagger=1, bigsword=2, bow=3, dualswords=4}
    for _, row in ipairs(Balance.Weapons) do
        local model = Weapons.CloneTestDisplay(row.type)
        if model then
            local tier = math.floor(row.level / 5)
            local point = origin:PointToWorldSpace(Vector3.new(-8 - tier * 6, -CharacterConfig.RootAnchorOffset, -12 - (types[row.type] or 0) * 7))
            local surface = Arena.Surface(point, character)
            model:PivotTo(CFrame.new(surface) * origin.Rotation)
            local bounds, size = model:GetBoundingBox()
            model:PivotTo(model:GetPivot() + Vector3.new(0, surface.Y + 2 - bounds.Position.Y + size.Y / 2, 0))
            local color = Balance.Grade.Color(row.level)
            Appearance.Tint(model, color)
            local grade, required = Balance.Grade.ForLevel(row.level)
            local reference = model:FindFirstChildWhichIsA("BasePart", true)
            if reference then Appearance.Label(model, ("Оружие_%s · %s · %s\nreq %d · %d ATK"):format(row.id:sub(-3), row.type, grade, required, Balance.Rules.baseDamage + row.damage), color, reference) end
            model.Parent = parent
        end
    end
end
function Arena.LinePoint(origin: CFrame, index: number, spacing: number): Vector3
    -- One line across the forward half-plane; level 1 is directly in front of spawn.
    return origin:PointToWorldSpace(Vector3.new((index - 1) * spacing, -CharacterConfig.RootAnchorOffset, -24))
end
function Arena.GroupPoint(origin: CFrame, index: number, count: number, size: Vector3): Vector3
    local radius = math.max(9, count * (math.max(size.X, size.Z) + 2) / (2 * math.pi))
    local angle = (index - 1) * 2 * math.pi / count
    return origin:PointToWorldSpace(Vector3.new(math.sin(angle) * radius, -CharacterConfig.RootAnchorOffset, -math.cos(angle) * radius))
end
function Arena.Add(owner: Player, row: any, kind: string, point: Vector3, facing: Vector3, states: {any}, supports: Instance): Model?
    serial += 1
    -- The line uses the exact authored deck plane, never the surrounding terrain.
    local surface = point
    if kind ~= "line" then
        local grounded
        surface, grounded = Arena.Surface(point, owner.Character)
        if not grounded then Arena.Support(supports, point, 18) end
    end
    local yaw = math.deg(math.atan2(-facing.X, -facing.Z))
    local state = Spawner.AddTest({
        spawnId = "gameplay-test-" .. owner.UserId .. "-" .. serial,
        monsterSlug = "gremlin", position = {x=surface.X, y=surface.Y, z=surface.Z},
        spawnRadius = 0, homeRadiusStuds = 150, maxAlive = 1, respawnSeconds = 2,
        testOwner = owner.UserId, testKind = kind, testBalanceId = row.id,
        testNoRespawn = kind == "group", testYaw = yaw, testSurface = surface,
    })
    table.insert(states, state) -- Registered BEFORE any yielding construction.
    return Spawner.FillTest(state)
end
function Arena.Clear(states: {any})
    for _, state in ipairs(states) do Spawner.RemoveTest(state) end
    table.clear(states)
end
function Arena.Warp(character: Model, frame: CFrame)
    character:PivotTo(frame)
    for _, part in ipairs(character:GetDescendants()) do
        if part:IsA("BasePart") and not part.Anchored then
            part.AssemblyLinearVelocity = Vector3.zero
            part.AssemblyAngularVelocity = Vector3.zero
        end
    end
end
return table.freeze(Arena)

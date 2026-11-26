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
local Layout = require(script.Parent:WaitForChild("GameplayTestLayout"))
local SkillEffects = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("SkillEffects"))
local Players = game:GetService("Players")
local CameraSync = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterCameraSync"))
local Decorations = require(script.Parent:WaitForChild("GameplayWorldDecorations"))
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
    local nx,nz = math.max(1,math.ceil(width/1024)),math.max(1,math.ceil(depth/1024))
    local sx,sz=width/nx,depth/nz
    for x=1,nx do for z=1,nz do
        local part=Instance.new("Part")
        part.Name=name.."_"..x.."_"..z; part.Size=Vector3.new(sx,1,sz)
        part.CFrame=top*CFrame.new(-width/2+(x-0.5)*sx,-0.5,-depth/2+(z-0.5)*sz)
        part.Anchored=true; part.Material=Enum.Material.SmoothPlastic; part.Color=color
        part.TopSurface=Enum.SurfaceType.Smooth; part.BottomSurface=Enum.SurfaceType.Smooth; part.Parent=folder
    end end
    return folder
end

function Arena.BuildZonePlatform(parent: Instance, origin: CFrame, spacing: number, size: Vector3): any
    local layout=Layout.Build(origin,Balance.Monsters,Balance.MaxLevel,spacing,size,Balance.Test.maxGroup,if Balance.Test.skilledEnabled then Balance.SkilledMonsters else {})
    for _,platform in ipairs(layout.platforms) do
        deck(parent,platform.name,platform.top,platform.size.X,platform.size.Z,platform.color)
    end
    for index,box in pairs(layout.boxes) do
        local folder=Instance.new("Folder"); folder.Name="Bounds_"..index; folder.Parent=parent
        local half=box.size.X/2
        for side=0,3 do
            local rotation=CFrame.Angles(0,math.rad(side*90),0)
            local wall=Instance.new("Part"); wall.Name="Wall_"..side
            wall.Size=Vector3.new(box.size.X,box.size.Y,1)
            wall.CFrame=box.top*rotation*CFrame.new(0,box.size.Y/2,-half)
            wall.Anchored=true; wall.CanCollide=false; wall.CanTouch=false; wall.CanQuery=false
            wall.Material=Enum.Material.SmoothPlastic; wall.Color=box.color; wall.Transparency=0.82; wall.Parent=folder
        end
        local anchor=Instance.new("Part"); anchor.Name="ZoneLabel"; anchor.Anchored=true; anchor.CanCollide=false; anchor.CanTouch=false; anchor.CanQuery=false
        anchor.Transparency=1; anchor.Size=Vector3.one; anchor.CFrame=box.entry+Vector3.yAxis*15; anchor.Parent=folder
        local gui=Instance.new("BillboardGui"); gui.Size=UDim2.fromOffset(330,75); gui.MaxDistance=450; gui.Adornee=anchor; gui.Parent=anchor
        local label=Instance.new("TextLabel"); label.Size=UDim2.fromScale(1,1); label.BackgroundTransparency=1; label.Text=box.name.." · LVL "..box.low.."–"..box.high; label.TextColor3=box.color; label.TextStrokeTransparency=0.15; label.Font=Enum.Font.GothamBold; label.TextScaled=true; label.Parent=gui
    end
    Decorations.Build(parent, layout)
    local function markerFor(id: string, slot: any)
        local marker=Instance.new("Part"); marker.Name="Spawn_"..id; marker.Size=Vector3.new(8,0.1,8); marker.Position=slot.point+Vector3.yAxis*0.05
        marker.Anchored=true; marker.CanCollide=false; marker.CanTouch=false; marker.CanQuery=false; marker.Transparency=0.45; marker.Color=layout.boxes[slot.zone].color; marker.Parent=parent
    end
    for id,slot in pairs(layout.slots) do markerFor(id,slot) end
    for index,item in ipairs(layout.extraSlots) do markerFor(item.row.id.."_extra_"..index,item.slot) end
    return layout
end

function Arena.ShowWeapons(parent: Instance, origin: CFrame, character: Model)
    local types = {sword=0, dagger=1, bigsword=2, bow=3, dualswords=4}
    for _, row in ipairs(Balance.Weapons) do
        local model = Weapons.CloneTestDisplay(row.type)
        if model then
            local tier = math.floor(row.level / 5)
            local point = origin:PointToWorldSpace(Vector3.new(-20 - tier * 6, -CharacterConfig.RootAnchorOffset, -14 + (types[row.type] or 0) * 7))
            local surface = Arena.Surface(point, character)
            model:PivotTo(CFrame.new(surface) * origin.Rotation)
            local bounds, size = model:GetBoundingBox()
            model:PivotTo(model:GetPivot() + Vector3.new(0, surface.Y + 2 - bounds.Position.Y + size.Y / 2, 0))
            local color = Balance.Grade.Color(row.level)
            Appearance.Tint(model, color)
            local grade, required = Balance.Grade.ForLevel(row.level)
            local reference = model:FindFirstChildWhichIsA("BasePart", true)
            if reference then Appearance.Label(model, ("Оружие_%s · %s · %s\nreq %d · %g ATK"):format(row.id:sub(-3), row.type, grade, required, Balance.BaseDamageAt(row.level) + row.damage), color, reference) end
            model.Parent = parent
        end
    end
end
function Arena.GroupPoint(origin: CFrame, index: number, count: number, size: Vector3, startDistance: number?): Vector3
    local radius = startDistance or math.max(9, count * (math.max(size.X, size.Z) + 2) / (2 * math.pi))
    local angle = (index - 1) * 2 * math.pi / count
    return origin:PointToWorldSpace(Vector3.new(math.sin(angle) * radius, -CharacterConfig.RootAnchorOffset, -math.cos(angle) * radius))
end
function Arena.Add(owner: Player, row: any, kind: string, point: Vector3, facing: Vector3, states: {any}, supports: Instance, slot: any?): Model?
    serial += 1
    -- Zone points use the exact deck plane, never surrounding terrain.
    local surface = point
    if kind ~= "zone" then
        local grounded
        surface, grounded = Arena.Surface(point, owner.Character)
        if not grounded then Arena.Support(supports, point, 18) end
    end
    local yaw = math.deg(math.atan2(-facing.X, -facing.Z))
    local state = Spawner.AddTest({
        spawnId = "gameplay-test-" .. owner.UserId .. "-" .. serial,
        monsterSlug = "gremlin", position = {x=surface.X, y=surface.Y, z=surface.Z},
        spawnRadius = 0, homeRadiusStuds = if slot and slot.homeRadius then slot.homeRadius else 150, maxAlive = 1, respawnSeconds = 2,
        testOwner = owner.UserId, testKind = kind, testBalanceId = row.id,
        testNoRespawn = kind == "group", testYaw = yaw, testSurface = surface,
        testZone = if slot then slot.zone else nil,
    })
    table.insert(states, state) -- Registered BEFORE any yielding construction.
    return Spawner.FillTest(state)
end
function Arena.Clear(states: {any})
    for _, state in ipairs(states) do Spawner.RemoveTest(state) end
    table.clear(states)
end
function Arena.Warp(character: Model, frame: CFrame, preserveBuffs: boolean?)
    SkillEffects.Clear(character,preserveBuffs)
    character:PivotTo(frame)
    local manager = character:FindFirstChildWhichIsA("ControllerManager", true)
    if manager then manager.FacingDirection = frame.LookVector end
    local player = Players:GetPlayerFromCharacter(character)
    if player then CameraSync.Align(player, character, frame) end
    for _, part in ipairs(character:GetDescendants()) do
        if part:IsA("BasePart") and not part.Anchored then
            part.AssemblyLinearVelocity = Vector3.zero
            part.AssemblyAngularVelocity = Vector3.zero
        end
    end
end
return table.freeze(Arena)

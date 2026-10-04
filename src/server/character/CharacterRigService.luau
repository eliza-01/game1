local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))

local CharacterRigService = {}

local function getSpawnLocation(player: Player): SpawnLocation?
    if player.RespawnLocation and player.RespawnLocation.Enabled then
        return player.RespawnLocation
    end
    for _, object in Workspace:GetDescendants() do
        if object:IsA("SpawnLocation") and object.Enabled then
            return object
        end
    end
    return nil
end

function CharacterRigService.SpawnCFrame(player: Player): CFrame
    local spawnLocation = getSpawnLocation(player)
    if spawnLocation then
        local position = spawnLocation.Position + Vector3.new(
            0,
            spawnLocation.Size.Y * 0.5 + CharacterConfig.RootAnchorOffset + CharacterConfig.SpawnClearance,
            0
        )
        local _, yaw, _ = spawnLocation.CFrame:ToOrientation()
        return CFrame.new(position) * CFrame.Angles(0, yaw, 0)
    end
    return CFrame.new(0, CharacterConfig.RootAnchorOffset + 8, 0)
end

local function createRoot(character: Model, spawnCFrame: CFrame): BasePart
    local root = Instance.new("Part")
    root.Name = "RootCollider"
    root.Size = CharacterConfig.RootColliderSize
    root.CFrame = spawnCFrame
    root.Transparency = 1
    root.CastShadow = false
    root.Anchored = false
    root.CanCollide = false
    root.CanTouch = false
    root.CanQuery = true
    root.Massless = true
    root.TopSurface = Enum.SurfaceType.Smooth
    root.BottomSurface = Enum.SurfaceType.Smooth
    root.Parent = character
    character.PrimaryPart = root
    return root
end

local function createNavigationRoot(character: Model, root: BasePart): BasePart
    local navigationRoot = Instance.new("Part")
    navigationRoot.Name = "NavigationRoot"
    navigationRoot.Size = CharacterConfig.NavigationRootSize
    navigationRoot.CFrame = root.CFrame + Vector3.new(
        0,
        CharacterConfig.NavigationCenterOffset - CharacterConfig.RootAnchorOffset,
        0
    )
    navigationRoot.Transparency = 1
    navigationRoot.CastShadow = false
    navigationRoot.Anchored = false
    navigationRoot.CanCollide = true
    navigationRoot.CanTouch = false
    navigationRoot.CanQuery = false
    navigationRoot.Massless = false
    navigationRoot.TopSurface = Enum.SurfaceType.Smooth
    navigationRoot.BottomSurface = Enum.SurfaceType.Smooth
    navigationRoot.Parent = character

    local weld = Instance.new("WeldConstraint")
    weld.Name = "RootColliderWeld"
    weld.Part0 = navigationRoot
    weld.Part1 = root
    weld.Parent = navigationRoot
    return navigationRoot
end

local function createPhysicsController(character: Model, navigationRoot: BasePart): (ControllerManager, BasePart)
    local controllerManager = Instance.new("ControllerManager")
    controllerManager.Name = "ControllerManager"
    controllerManager.RootPart = navigationRoot
    controllerManager.BaseMoveSpeed = CharacterMovementConfig.RobloxSpeed(
        character:GetAttribute("CharacterArchetype"),
        character:GetAttribute("MoveSpeed"),
        "Run"
    )
    controllerManager.BaseTurnSpeed = CharacterConfig.TurnSpeed
    controllerManager.UpDirection = Vector3.yAxis
    controllerManager.MovingDirection = Vector3.zero
    controllerManager.FacingDirection = navigationRoot.CFrame.LookVector
    controllerManager.Parent = character

    local groundController = Instance.new("GroundController")
    groundController.Name = "GroundController"
    groundController.GroundOffset = CharacterConfig.GroundOffset
    groundController.AccelerationTime = 0.08
    groundController.DecelerationTime = 0.08
    groundController.Friction = 2
    groundController.FrictionWeight = 100
    groundController.Parent = controllerManager

    local airController = Instance.new("AirController")
    airController.Name = "AirController"
    airController.MaintainAngularMomentum = false
    airController.MaintainLinearMomentum = true
    airController.Parent = controllerManager

    local sensorPart = Instance.new("Part")
    sensorPart.Name = "GroundSensorPart"
    sensorPart.Size = navigationRoot.Size
    sensorPart.CFrame = navigationRoot.CFrame
    sensorPart.Transparency = 1
    sensorPart.CastShadow = false
    sensorPart.Anchored = false
    sensorPart.CanCollide = false
    sensorPart.CanTouch = false
    sensorPart.CanQuery = false
    sensorPart.Massless = true
    sensorPart.Parent = character

    local sensorWeld = Instance.new("WeldConstraint")
    sensorWeld.Name = "GroundSensorWeld"
    sensorWeld.Part0 = navigationRoot
    sensorWeld.Part1 = sensorPart
    sensorWeld.Parent = navigationRoot

    controllerManager.ActiveController = groundController
    return controllerManager, sensorPart
end

local function createGroundSensor(controllerManager: ControllerManager, sensorPart: BasePart)
    local sensor = Instance.new("ControllerPartSensor")
    sensor.Name = "GroundSensor"
    sensor.SensorMode = Enum.SensorMode.Floor
    sensor.SearchDistance = CharacterConfig.GroundSearchDistance
    sensor.Parent = sensorPart
    controllerManager.GroundSensor = sensor
end

local function sensedFloorY(character: Model, root: BasePart): (number, string)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { character }
    params.RespectCanCollide = true
    local distance = CharacterConfig.GroundSearchDistance
        + CharacterConfig.RootColliderSize.Y
        + CharacterConfig.SpawnClearance
        + 1
    local result = Workspace:Raycast(root.Position, Vector3.new(0, -distance, 0), params)
    if result then
        return result.Position.Y, "Raycast"
    end
    return root.Position.Y - CharacterConfig.RootAnchorOffset, "ControllerFallback"
end

local function ensureAnimationHost(visual: Model): AnimationController
    local host = visual:FindFirstChildOfClass("AnimationController")
    if not host then
        host = visual:FindFirstChildWhichIsA("AnimationController", true)
        if host then
            host.Parent = visual
        else
            host = Instance.new("AnimationController")
            host.Name = "AnimationController"
            host.Parent = visual
        end
    end

    for _, descendant in visual:GetDescendants() do
        if descendant:IsA("AnimationController") and descendant ~= host then
            descendant:Destroy()
        end
    end

    local animator = host:FindFirstChildOfClass("Animator")
    if not animator then
        animator = Instance.new("Animator")
        animator.Name = "Animator"
        animator.Parent = host
    end
    return host
end

local function normalizeTemplate(template: Model): (Model, Model)
    local cloned = template:Clone()
    local visual: Model
    local importedRig: Model

    local managedRig = cloned:FindFirstChild("ImportedRig")
    if managedRig and managedRig:IsA("Model") then
        visual = cloned
        visual.Name = "Visual"
        importedRig = managedRig
    else
        visual = Instance.new("Model")
        visual.Name = "Visual"
        cloned.Name = "ImportedRig"
        cloned.Parent = visual
        importedRig = cloned
    end

    ensureAnimationHost(visual)
    for _, object in visual:GetDescendants() do
        if object:IsA("Humanoid") then
            object:Destroy()
        elseif object:IsA("BasePart") then
            object.Anchored = false
            object.CanCollide = false
            object.CanTouch = false
            object.CanQuery = false
            object.Massless = true
        end
    end
    return visual, importedRig
end

local function createBootstrapCompatibilityRoot(importedRig: Model): BasePart
    local boxCFrame, boxSize = importedRig:GetBoundingBox()
    local root = Instance.new("Part")
    root.Name = "RootPart"
    root.Size = CharacterConfig.VisualRootAnchorSize
    root.CFrame = CFrame.new(
        boxCFrame.Position.X,
        boxCFrame.Position.Y - boxSize.Y * 0.5,
        boxCFrame.Position.Z
    )
    root.Transparency = 1
    root.CastShadow = false
    root.Anchored = false
    root.CanCollide = false
    root.CanTouch = false
    root.CanQuery = false
    root.Massless = true
    root:SetAttribute("Game1BootstrapCompatibilityRoot", true)
    root.Parent = importedRig

    for _, object in importedRig:GetDescendants() do
        if object:IsA("BasePart") and object ~= root then
            local weld = Instance.new("WeldConstraint")
            weld.Name = "BootstrapCompatibilityRootWeld"
            weld.Part0 = root
            weld.Part1 = object
            weld.Parent = root
        end
    end
    return root
end

local function visualRoot(importedRig: Model, allowBootstrapCompatibility: boolean): (BasePart?, boolean)
    local root = importedRig:FindFirstChild("RootPart", true)
    if root and root:IsA("BasePart") then
        root.Size = CharacterConfig.VisualRootAnchorSize
        return root, true
    end
    if allowBootstrapCompatibility then
        return createBootstrapCompatibilityRoot(importedRig), false
    end
    warn("[game1] registered character template is missing ImportedRig/RootPart; sync it through the game1 Studio bridge")
    return nil, false
end

local function partLowestWorldY(part: BasePart): number
    local half = part.Size * 0.5
    local lowest = math.huge
    for x = -1, 1, 2 do
        for y = -1, 1, 2 do
            for z = -1, 1, 2 do
                local corner = part.CFrame:PointToWorldSpace(Vector3.new(
                    half.X * x,
                    half.Y * y,
                    half.Z * z
                ))
                lowest = math.min(lowest, corner.Y)
            end
        end
    end
    return lowest
end

local function lowestVisibleGeometryY(visual: Model, visualRootPart: BasePart): (number?, number)
    local lowest = math.huge
    local count = 0
    for _, object in visual:GetDescendants() do
        if object:IsA("BasePart")
            and object ~= visualRootPart
            and object.Transparency < 1
        then
            lowest = math.min(lowest, partLowestWorldY(object))
            count += 1
        end
    end
    if count == 0 then
        return nil, 0
    end
    return lowest, count
end

local function placeAuthoredVisual(visual: Model, visualRootPart: BasePart, root: BasePart, floorY: number): (number, number)
    local _, rootYaw, _ = root.CFrame:ToOrientation()
    local sourcePivotRotation = visual:GetPivot().Rotation
    visual:PivotTo(
        CFrame.new(root.Position.X, floorY, root.Position.Z)
        * CFrame.Angles(0, rootYaw, 0)
        * sourcePivotRotation
    )

    -- RootPart is a rig helper, not the foot-contact plane. Generic skinned FBX
    -- assets can have a perfectly valid RootPart/pivot while the rendered mesh
    -- extends below it. Match the reference runtime contract: align the lowest
    -- visible geometry to the measured world floor, then weld the authored root.
    local lowestY, visibleParts = lowestVisibleGeometryY(visual, visualRootPart)
    if lowestY == nil then
        lowestY = visualRootPart.Position.Y
    end
    local correctionY = floorY + CharacterConfig.VisualGroundClearance - lowestY
    visual:PivotTo(visual:GetPivot() + Vector3.new(0, correctionY, 0))
    return correctionY, visibleParts
end

local function placeCompatibilityVisual(visual: Model, visualRootPart: BasePart, root: BasePart, floorY: number)
    local _, rootYaw, _ = root.CFrame:ToOrientation()
    local targetRootCFrame = CFrame.new(
        root.Position.X,
        floorY + CharacterConfig.VisualGroundClearance,
        root.Position.Z
    ) * CFrame.Angles(0, rootYaw, 0)

    -- The imported rig is already upright in ServerStorage. Move it as one rigid
    -- assembly from its compatibility RootPart instead of rebuilding mesh rotation.
    local delta = targetRootCFrame * visualRootPart.CFrame:Inverse()
    visual:PivotTo(delta * visual:GetPivot())
end

local function attachVisual(
    character: Model,
    root: BasePart,
    template: Model,
    allowBootstrapCompatibility: boolean
): (Model?, BasePart?)
    local visual, importedRig = normalizeTemplate(template)
    visual.Parent = character

    local visualRootPart, authoredRoot = visualRoot(importedRig, allowBootstrapCompatibility)
    if not visualRootPart then
        visual:Destroy()
        return nil, nil
    end
    local floorY, floorSource = sensedFloorY(character, root)
    local groundCorrectionY = 0
    local groundParts = 0
    if authoredRoot then
        groundCorrectionY, groundParts = placeAuthoredVisual(visual, visualRootPart, root, floorY)
    else
        placeCompatibilityVisual(visual, visualRootPart, root, floorY)
    end

    character:SetAttribute("VisualRootSource", if authoredRoot then "authored" else "bootstrap_compatibility")
    character:SetAttribute("VisualGroundCorrectionY", groundCorrectionY)
    character:SetAttribute("VisualGroundParts", groundParts)
    character:SetAttribute("VisualFootContactSource", if authoredRoot then "visible_geometry" else "bootstrap_root")
    character:SetAttribute("VisualGroundFloorY", floorY)
    character:SetAttribute("VisualGroundSource", floorSource)
    character:SetAttribute("VisualRootAnchorSize", tostring(CharacterConfig.VisualRootAnchorSize))
    character:SetAttribute("RootGroundClearance", CharacterConfig.RootGroundClearance)
    character:SetAttribute("NavigationHipHeight", CharacterConfig.NavigationHipHeight)
    character:SetAttribute("NavigationCenterOffset", CharacterConfig.NavigationCenterOffset)
    character:SetAttribute("NavigationGroundOffset", CharacterConfig.GroundOffset)

    local weld = Instance.new("WeldConstraint")
    weld.Name = "VisualRootWeld"
    weld.Part0 = root
    weld.Part1 = visualRootPart
    weld.Parent = root
    return visual, visualRootPart
end

function CharacterRigService.Build(
    character: Model,
    spawnCFrame: CFrame,
    template: Model,
    allowBootstrapCompatibility: boolean
): any?
    local root = createRoot(character, spawnCFrame)
    local navigationRoot = createNavigationRoot(character, root)
    local controllerManager, groundSensorPart = createPhysicsController(character, navigationRoot)
    local visual, visualRootPart = attachVisual(character, root, template, allowBootstrapCompatibility)
    if not visual or not visualRootPart then
        return nil
    end
    return {
        root = root,
        navigationRoot = navigationRoot,
        controllerManager = controllerManager,
        groundSensorPart = groundSensorPart,
        visual = visual,
        visualRootPart = visualRootPart,
    }
end

function CharacterRigService.Finish(rig: any)
    createGroundSensor(rig.controllerManager, rig.groundSensorPart)
end

return table.freeze(CharacterRigService)

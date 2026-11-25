-- Roblox Studio: StarterPlayer.StarterPlayerScripts.Game1Client.CameraController (ModuleScript)
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Game1Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Game1Shared:WaitForChild("character")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local CameraHeading = require(CharacterShared:WaitForChild("CharacterCameraHeading"))
local GameOptions = require(Game1Shared:WaitForChild("GameOptions"))
local PublishedDebugAccess = require(Game1Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local AutoAimTargeting = require(script.Parent:WaitForChild("MobileAutoAimTargeting"))

local CameraController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local root: BasePart? = nil
local rotating = false
local targetYaw = 0
local pendingAlignment: {character: Model, yaw: number}? = nil
local cameraSettings = GameOptions.CameraSettings()
local creationView: any? = nil
local targetPitch = math.rad(cameraSettings.pitchDegrees)
local distance = cameraSettings.distance
local discardNextMouseDelta = false
local autoAimMonster: Model? = nil
local autoAimBone: Bone? = nil
local autoAimNeedsSnap = false
local autoAimChanged = Instance.new("BindableEvent")

local raycastParameters = RaycastParams.new()
raycastParameters.FilterType = Enum.RaycastFilterType.Exclude
raycastParameters.IgnoreWater = false

local function clearAutoAim()
    if autoAimMonster then
        autoAimMonster = nil
        autoAimBone = nil
        autoAimNeedsSnap = false
        autoAimChanged:Fire(nil)
    end
end


-- Apply to orbit state, not Camera.CFrame: the existing render step owns
-- the camera and would otherwise overwrite an external one-shot CFrame.
local function alignAfterTeleport(movedCharacter: Model, forward: Vector3)
    if typeof(movedCharacter) ~= "Instance" or not movedCharacter:IsA("Model")
        or movedCharacter ~= localPlayer.Character or typeof(forward) ~= "Vector3" then return end
    local yaw = CameraHeading.Yaw(forward)
    if yaw == nil then return end
    if character ~= movedCharacter or not root then
        pendingAlignment = {character = movedCharacter, yaw = yaw}
        return
    end
    pendingAlignment = nil
    clearAutoAim()
    targetYaw = yaw
    discardNextMouseDelta = rotating
end

local function setCharacter(newCharacter: Model)
    clearAutoAim()
	character = newCharacter
	root = nil

	local newRoot = newCharacter:WaitForChild("RootCollider", 10)
	if character ~= newCharacter or localPlayer.Character ~= newCharacter then return end
	if newRoot and newRoot:IsA("BasePart") then
		root = newRoot
		local pending = pendingAlignment
		pendingAlignment = nil
		targetYaw = if pending and pending.character == newCharacter then pending.yaw
			else CameraHeading.Yaw(newRoot.CFrame.LookVector) or 0
		raycastParameters.FilterDescendantsInstances = { newCharacter }
	end
end


local function releaseMouse()
	rotating = false
	discardNextMouseDelta = false
	if UserInputService.MouseBehavior == Enum.MouseBehavior.LockCurrentPosition then
		UserInputService.MouseBehavior = Enum.MouseBehavior.Default
	end
end

local function updateCameraInput(_deltaTime: number)
	if creationView then return end
	if not rotating then
		return
	end

	-- Sample mouse motion once per render frame at the dedicated Input priority.
	-- Processing every InputChanged mouse packet can make a scripted camera advance
	-- in uneven chunks when mouse polling rate and render rate do not line up.
	local mouseDelta = UserInputService:GetMouseDelta()
	if discardNextMouseDelta then
		-- LockCurrentPosition can expose a stale/re-centering delta on the first
		-- frame after RMB capture. Consume it without rotating the camera.
		discardNextMouseDelta = false
		return
	end

	if mouseDelta == Vector2.zero then
		return
	end

    clearAutoAim()
	targetYaw -= mouseDelta.X * CharacterConfig.CameraMouseSensitivity
	targetPitch = math.clamp(
		targetPitch - mouseDelta.Y * CharacterConfig.CameraMouseSensitivity,
		CharacterConfig.CameraMinPitch,
		CharacterConfig.CameraMaxPitch
	)
end

local function setCameraOrbit(camera: Camera, currentRoot: BasePart)
    camera.CameraType = Enum.CameraType.Scriptable
    camera.FieldOfView = CharacterConfig.CameraFieldOfView
    local renderedRootCFrame = currentRoot:GetRenderCFrame()
    local target = renderedRootCFrame.Position + Vector3.new(0, cameraSettings.targetHeight, 0)
    local rotation = CFrame.Angles(0, targetYaw, 0) * CFrame.Angles(targetPitch, 0, 0)
    local viewport = camera.ViewportSize
    local aspect = if viewport.Y > 1 then viewport.X / viewport.Y else 1
    local halfHeight = distance * math.tan(math.rad(camera.FieldOfView) * 0.5)
    local halfWidth = halfHeight * aspect
    local screenShift = rotation.RightVector * ((0.5 - cameraSettings.characterX) * 2 * halfWidth)
        + rotation.UpVector * ((cameraSettings.characterY - 0.5) * 2 * halfHeight)
    target += screenShift
    local desiredPosition = target + rotation:VectorToWorldSpace(Vector3.new(0, 0, distance))
    local cameraPosition = desiredPosition
    local result = Workspace:Raycast(target, desiredPosition - target, raycastParameters)
    if result then cameraPosition = result.Position + result.Normal * CharacterConfig.CameraCollisionPadding end
    camera.CFrame = CFrame.lookAt(cameraPosition, target, Vector3.yAxis)
    camera.Focus = CFrame.new(target)
end

local function updateCamera(_deltaTime: number)
    if creationView then
        local camera = Workspace.CurrentCamera
        if not camera then return end
        local view = creationView
        view.elapsed = math.min(view.elapsed + _deltaTime, view.duration)
        local fraction = if view.duration <= 0 then 1 else view.elapsed / view.duration
        -- smoothstep avoids a visible jolt when switching from body to face.
        local alpha = fraction * fraction * (3 - 2 * fraction)
        camera.CameraType = Enum.CameraType.Scriptable
        camera.CFrame = view.start:Lerp(view.target, alpha)
        camera.FieldOfView = view.fromFov + (view.toFov - view.fromFov) * alpha
        camera.Focus = CFrame.new(camera.CFrame.Position + camera.CFrame.LookVector * 12)
        return
    end
    local currentRoot = root
    local camera = Workspace.CurrentCamera
    if not currentRoot or not currentRoot.Parent or not camera then return end

    local focusPoint = if autoAimMonster and autoAimBone
        then AutoAimTargeting.Point(autoAimMonster, autoAimBone) else nil
    if autoAimMonster and not focusPoint then clearAutoAim() end

    if focusPoint then
        local delta = focusPoint - currentRoot.Position
        local radius = math.clamp(tonumber((GameOptions.HealthUiSettings(
            if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
            then "mobile" else "desktop").monster or {}).maxDistanceStuds) or 100, 20, 800)
        if delta.Magnitude > radius then
            clearAutoAim()
            focusPoint = nil
        end
    end

    if focusPoint then
        -- The first press snaps towards targets even behind the camera.
        -- Following frames preserve the last solution: only small corrections
        -- are needed as the neck moves, avoiding repeated full camera searches.
        if autoAimNeedsSnap then
            local pivot = currentRoot:GetRenderCFrame().Position + Vector3.new(0, cameraSettings.targetHeight, 0)
            local delta = focusPoint - pivot
            local flat = Vector3.new(delta.X, 0, delta.Z)
            if flat.Magnitude > 0.01 then
                targetYaw = math.atan2(-delta.X, -delta.Z)
                targetPitch = math.clamp(math.atan2(delta.Y, flat.Magnitude),
                    CharacterConfig.CameraMinPitch, CharacterConfig.CameraMaxPitch)
            end
            autoAimNeedsSnap = false
        end
        -- The character/cursor are not necessarily centred. WorldToViewportPoint
        -- accounts for the actual viewport and collision-limited camera CFrame.
        local size = camera.ViewportSize
        local pixelRadians = 2 * math.tan(math.rad(camera.FieldOfView) * 0.5) / math.max(size.Y, 1)
        for _ = 1, 2 do
            setCameraOrbit(camera, currentRoot)
            local projected = camera:WorldToViewportPoint(focusPoint)
            if projected.Z <= 0 then break end
            local errorX = projected.X - size.X * cameraSettings.cursorX
            local errorY = projected.Y - size.Y * cameraSettings.cursorY
            if math.abs(errorX) + math.abs(errorY) < 1.5 then break end
            targetYaw -= math.clamp(errorX * pixelRadians, -0.5, 0.5)
            targetPitch = math.clamp(targetPitch - math.clamp(errorY * pixelRadians, -0.5, 0.5),
                CharacterConfig.CameraMinPitch, CharacterConfig.CameraMaxPitch)
        end
    end
    setCameraOrbit(camera, currentRoot)
end

-- Exactly one CameraController controls both world and Character Creation cameras.
-- Stage names/order are stable authoring identifiers; capture points live in Place.
local CREATION_STAGES = {
    SelectionOverview = true, MaleFullBody = true, FemaleFullBody = true,
    MaleFace = true, FemaleFace = true,
}

function CameraController.ShowCreationView(stage: string, duration: number?): boolean
    if not CREATION_STAGES[stage] then return false end
    local options = GameOptions.CharacterCreationSettings()
    local view = (options.views or {})[stage]
    if not view or type(view.cframe) ~= "table" or #view.cframe ~= 12 then return false end
    local target = CFrame.new(table.unpack(view.cframe))
    if options.useStudioAnchors then
        local places = Workspace:FindFirstChild("Places")
        local scene = places and places:FindFirstChild("Character Creation")
        local folder = scene and scene:FindFirstChild("Game1CharacterCreationCameras")
        local point = folder and folder:FindFirstChild(stage)
        if point and point:IsA("BasePart") then target = point.CFrame end
    end
    local camera = Workspace.CurrentCamera
    if not camera then return false end
    releaseMouse()
    clearAutoAim()
    creationView = {
        start = camera.CFrame, target = target,
        fromFov = camera.FieldOfView, toFov = math.clamp(tonumber(view.fov) or 70, 25, 100),
        elapsed = 0, duration = math.clamp(tonumber(duration) or 0.9, 0, 5),
    }
    return true
end

-- Optional independently authored Character Selection scene. Until its anchors
-- exist, the existing SelectionOverview is used rather than invented coordinates.
-- CharacterSelectionCamera and CharacterSelectionPreviewPoint are resolved as
-- one pair by the creation controller (shared CharacterSelectionScene contract).
function CameraController.ShowCharacterSelectionView(archetype: string?, duration: number?, anchors: any?): boolean
    if not anchors then
        local name = if archetype == "human_male" then "MaleFullBody"
            else if archetype == "human_female" then "FemaleFullBody"
            else "SelectionOverview"
        return CameraController.ShowCreationView(name, duration)
    end
    local camera = Workspace.CurrentCamera
    if not camera then return false end
    releaseMouse()
    clearAutoAim()
    creationView = {
        start = camera.CFrame, target = anchors.camera,
        fromFov = camera.FieldOfView,
        toFov = anchors.fov,
        elapsed = 0, duration = math.clamp(tonumber(duration) or 0.9, 0, 5),
    }
    return true
end

-- Release only when the replicated gameplay root is bound to this camera.
-- The menu keeps its transition curtain up until this returns true.
function CameraController.ClearCreationView(): boolean
    local camera = Workspace.CurrentCamera
    if not camera or not root or not root:IsDescendantOf(Workspace) or character ~= localPlayer.Character then return false end
    creationView = nil
    releaseMouse()
    clearAutoAim()
    targetPitch = math.rad(cameraSettings.pitchDegrees)
    distance = cameraSettings.distance
    setCameraOrbit(camera, root)
    return true
end

local CAMERA_LIMITS = {
    targetHeight = {0, 12}, distance = {4, 18}, pitchDegrees = {-65, 60},
    characterX = {0.2, 0.8}, characterY = {0.2, 0.8},
    cursorX = {0.1, 0.9}, cursorY = {0.1, 0.9},
    mobileLookSpeed = {0.25, 4},
}

function CameraController.GetSettings(): {[string]: number}
    return table.clone(cameraSettings)
end

function CameraController.ApplyDebug(settings: {[string]: number}): boolean
    if not PublishedDebugAccess.ClientAllowed() then return false end
    local replacement = table.clone(cameraSettings)
    for key, bounds in CAMERA_LIMITS do
        local value = settings[key]
        if type(value) ~= "number" or value ~= value or value == math.huge or value == -math.huge
            or value < bounds[1] or value > bounds[2] then
            return false
        end
        replacement[key] = value
    end
    local oldPitch = cameraSettings.pitchDegrees
    cameraSettings = replacement
    distance = cameraSettings.distance
    if math.abs(cameraSettings.pitchDegrees - oldPitch) > 1e-6 then
        targetPitch = math.rad(cameraSettings.pitchDegrees)
    end
    local gui = localPlayer:FindFirstChild("PlayerGui")
    local reticle = gui and gui:FindFirstChild("Game1AimReticle")
    local dot = reticle and reticle:FindFirstChild("Dot")
    if dot and dot:IsA("GuiObject") then
        dot.Position = UDim2.fromScale(cameraSettings.cursorX, cameraSettings.cursorY)
    end
    return true
end

function CameraController.CursorPoint(): Vector2
    return Vector2.new(cameraSettings.cursorX, cameraSettings.cursorY)
end

function CameraController.AutoAimTarget(): Model?
    return autoAimMonster
end

function CameraController.AutoAimChanged(callback: (Model?) -> ()): RBXScriptConnection
    return autoAimChanged.Event:Connect(callback)
end

function CameraController.ToggleAutoAim(): boolean
    if autoAimMonster then
        clearAutoAim()
        return false
    end
    if not UserInputService.TouchEnabled or not character or not root then return false end
    local profile = GameOptions.HealthUiSettings(
        if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled then "mobile" else "desktop")
    local radius = math.clamp(tonumber((profile.monster or {}).maxDistanceStuds) or 100, 20, 800)
    local selected, bone = AutoAimTargeting.Acquire(character, radius)
    if not selected or not bone then return false end
    autoAimMonster, autoAimBone = selected, bone
    autoAimNeedsSnap = true
    autoAimChanged:Fire(selected)
    return true
end

function CameraController.GetAimRay(): (Vector3?, Vector3?)
    local camera = Workspace.CurrentCamera
    if not camera then return nil, nil end
    local v = camera.ViewportSize
    local ray = camera:ViewportPointToRay(v.X * cameraSettings.cursorX, v.Y * cameraSettings.cursorY)
    if ray.Direction.Magnitude <= 1e-6 then return nil, nil end
    return ray.Origin, ray.Direction.Unit
end

-- The touch adapter owns gesture recognition; this controller only consumes deltas.
function CameraController.RotateTouch(delta: Vector2)
    clearAutoAim()
    local sensitivity = CharacterConfig.CameraTouchSensitivity * GameOptions.MobileCameraSpeed()
	targetYaw -= delta.X * sensitivity
	targetPitch = math.clamp(
		targetPitch - delta.Y * sensitivity,
		CharacterConfig.CameraMinPitch,
		CharacterConfig.CameraMaxPitch
	)
end

function CameraController.PinchZoom(previousGap: number, currentGap: number)
	if previousGap <= 5 or currentGap <= 5 then
		return
	end
	-- A widening pinch zooms in. Bound malformed input spikes without smoothing.
	local ratio = math.clamp(previousGap / currentGap, 0.7, 1.4)
	distance = math.clamp(
		distance * ratio,
		CharacterConfig.CameraMinDistance,
		CharacterConfig.CameraMaxDistance
	)
end

function CameraController.Start()
	if started then
		return
	end
	started = true

	UserInputService.InputBegan:Connect(function(input: InputObject, gameProcessed: boolean)
		if not creationView and input.UserInputType == CharacterConfig.InputBindings.CameraOrbit[1] then
			if UiInputGuard.BlocksWorldInput(input, gameProcessed) then
				return
			end
			rotating = true
			discardNextMouseDelta = true
			UserInputService.MouseBehavior = Enum.MouseBehavior.LockCurrentPosition
		end
	end)

	UserInputService.InputEnded:Connect(function(input: InputObject)
		if input.UserInputType == CharacterConfig.InputBindings.CameraOrbit[1] then
			releaseMouse()
		end
	end)

	UserInputService.InputChanged:Connect(function(input: InputObject, gameProcessed: boolean)
		-- Mouse movement is intentionally NOT handled here. Camera orbit input is
		-- sampled once per render frame in updateCameraInput().
		if not creationView and input.UserInputType == Enum.UserInputType.MouseWheel then
			if UiInputGuard.BlocksWorldInput(input, gameProcessed) then
				return
			end
			distance = math.clamp(
				distance - input.Position.Z * CharacterConfig.CameraZoomStep,
				CharacterConfig.CameraMinDistance,
				CharacterConfig.CameraMaxDistance
			)
		end
	end)

	UserInputService.WindowFocusReleased:Connect(releaseMouse)

	localPlayer.CharacterAdded:Connect(setCharacter)
	localPlayer.CharacterRemoving:Connect(function(removingCharacter)
		if pendingAlignment and pendingAlignment.character == removingCharacter then pendingAlignment = nil end
		if removingCharacter == character then
			character = nil
			root = nil
            clearAutoAim()
			releaseMouse()
		end
	end)

	if localPlayer.Character then
		task.spawn(setCharacter, localPlayer.Character)
	end

    task.spawn(function()
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes", 30)
        local event = remotes and remotes:WaitForChild(CameraHeading.RemoteName, 30)
        if not event or not event:IsA("RemoteEvent") then
            warn("[game1][camera] camera alignment remote unavailable")
            return
        end
        event.OnClientEvent:Connect(alignAfterTeleport)
    end)

	RunService:BindToRenderStep(
		"game1CameraInput",
		Enum.RenderPriority.Input.Value + 1,
		updateCameraInput
	)

	RunService:BindToRenderStep(
		"game1CustomCamera",
		Enum.RenderPriority.Camera.Value + 1,
		updateCamera
	)
end

return CameraController

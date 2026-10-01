-- Roblox Studio: StarterPlayer.StarterPlayerScripts.Game1Client.CameraController (ModuleScript)
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Game1Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterConfig = require(Game1Shared:WaitForChild("CharacterConfig"))

local CameraController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local root: BasePart? = nil
local rotating = false
local targetYaw = 0
local targetPitch = CharacterConfig.CameraPitch
local renderedYaw = 0
local renderedPitch = CharacterConfig.CameraPitch
local distance = CharacterConfig.CameraDistance
local discardNextMouseDelta = false

local raycastParameters = RaycastParams.new()
raycastParameters.FilterType = Enum.RaycastFilterType.Exclude
raycastParameters.IgnoreWater = false

local function setCharacter(newCharacter: Model)
	character = newCharacter
	root = nil

	local newRoot = newCharacter:WaitForChild("RootCollider", 10)
	if newRoot and newRoot:IsA("BasePart") then
		root = newRoot
		local look = newRoot.CFrame.LookVector
		targetYaw = math.atan2(-look.X, -look.Z)
		renderedYaw = targetYaw
		renderedPitch = targetPitch
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

local function updateCameraInput()
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

	targetYaw -= mouseDelta.X * CharacterConfig.CameraMouseSensitivity
	targetPitch = math.clamp(
		targetPitch - mouseDelta.Y * CharacterConfig.CameraMouseSensitivity,
		CharacterConfig.CameraMinPitch,
		CharacterConfig.CameraMaxPitch
	)
end

local function updateCamera(deltaTime: number)
	local currentRoot = root
	if not currentRoot or not currentRoot.Parent then
		return
	end

	local camera = Workspace.CurrentCamera
	if not camera then
		return
	end

	camera.CameraType = Enum.CameraType.Scriptable
	camera.FieldOfView = CharacterConfig.CameraFieldOfView

	-- Mouse deltas are quantized input samples. Keep the authoritative target angles
	-- exact, but render toward them with a frame-rate-independent exponential response.
	-- This removes the visible one-pixel/one-packet stepping without smoothing the
	-- character follow position itself.
	local response = CharacterConfig.CameraRotationResponse
	local blend = 1 - math.exp(-response * math.max(0, deltaTime))
	renderedYaw += (targetYaw - renderedYaw) * blend
	renderedPitch += (targetPitch - renderedPitch) * blend

	-- Follow the transform Roblox actually renders for the physics root.
	-- Reading .Position here samples the simulation transform and can make the
	-- whole world appear to stutter when render FPS is higher than physics FPS.
	local renderedRootCFrame = currentRoot:GetRenderCFrame()
	local target = renderedRootCFrame.Position + Vector3.new(0, CharacterConfig.CameraTargetHeight, 0)
	local rotation = CFrame.Angles(0, renderedYaw, 0) * CFrame.Angles(renderedPitch, 0, 0)
	local desiredPosition = target + rotation:VectorToWorldSpace(Vector3.new(0, 0, distance))
	local castDirection = desiredPosition - target

	local cameraPosition = desiredPosition
	local result = Workspace:Raycast(target, castDirection, raycastParameters)
	if result then
		cameraPosition = result.Position + result.Normal * CharacterConfig.CameraCollisionPadding
	end

	camera.CFrame = CFrame.lookAt(cameraPosition, target, Vector3.yAxis)
end

function CameraController.Start()
	if started then
		return
	end
	started = true

	UserInputService.InputBegan:Connect(function(input: InputObject, gameProcessed: boolean)
		if gameProcessed then
			return
		end
		if input.UserInputType == CharacterConfig.InputBindings.CameraOrbit[1] then
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
		if gameProcessed then
			return
		end

		-- Mouse movement is intentionally NOT handled here. Camera orbit input is
		-- sampled once per render frame in updateCameraInput().
		if input.UserInputType == Enum.UserInputType.MouseWheel then
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
		if removingCharacter == character then
			character = nil
			root = nil
			releaseMouse()
		end
	end)

	if localPlayer.Character then
		task.spawn(setCharacter, localPlayer.Character)
	end

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

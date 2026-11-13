-- Roblox Studio: StarterPlayer.StarterPlayerScripts.Game1Client.MovementController (ModuleScript)
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local Workspace = game:GetService("Workspace")

local Game1Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Game1Shared:WaitForChild("character")
local WeaponShared = Game1Shared:WaitForChild("weapon")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local WeaponAttackMovement = require(WeaponShared:WaitForChild("WeaponAttackMovement"))
local AttackConfig = require(Game1Shared:WaitForChild("combat"):WaitForChild("AttackConfig"))
local GameOptions = require(Game1Shared:WaitForChild("GameOptions"))
local JumpSettings = GameOptions.PlayerJumpSettings()

local MovementController = {}

local localPlayer = Players.LocalPlayer
local started = false
local keysDown: { [Enum.KeyCode]: boolean } = {}
local touchAxis = Vector2.zero
local touchMovementActive = false
local jumpRequested = false
local jumpInFlight = false
local fallForce: VectorForce? = nil
local fallAttachment: Attachment? = nil
local airLockUntil = 0
local facingLockDirection: Vector3? = nil
local facingLockUntil = 0
local aimFacingActive = false
local aimFacingLive = false
local aimFacingStartedAt = 0
local aimFacingEndsAt = 0
local aimFacingStartDirection: Vector3? = nil
local aimFacingTargetDirection: Vector3? = nil
local aimFacingMaxResidualYaw = 0
local movementLockUntil = 0
local movementMode = "Run"
local movementDirectionMode = "Forward"
local forcedWalk = false
local attackMovementActive = false
local attackMovementEndsAt = 0
local attackMovementMode = "Run"
local attackMovementRunSpeedMultiplier = 1

local character: Model? = nil
local root: BasePart? = nil
local navigationRoot: BasePart? = nil
local controllerManager: ControllerManager? = nil
local groundController: GroundController? = nil
local airController: AirController? = nil
local groundSensor: ControllerPartSensor? = nil

local function clearCharacter()
    if fallForce then fallForce:Destroy(); fallForce = nil end
    if fallAttachment then fallAttachment:Destroy(); fallAttachment = nil end
    jumpInFlight = false
	character = nil
	root = nil
	navigationRoot = nil
	controllerManager = nil
	groundController = nil
	airController = nil
	groundSensor = nil
	jumpRequested = false
	airLockUntil = 0
	facingLockDirection = nil
	facingLockUntil = 0
	aimFacingActive = false
	aimFacingLive = false
	aimFacingStartedAt = 0
	aimFacingEndsAt = 0
	aimFacingStartDirection = nil
	aimFacingTargetDirection = nil
	aimFacingMaxResidualYaw = 0
	movementLockUntil = 0
	movementMode = "Run"
	movementDirectionMode = "Forward"
	forcedWalk = false
	attackMovementActive = false
	attackMovementEndsAt = 0
	attackMovementMode = "Run"
	attackMovementRunSpeedMultiplier = 1
end

local function attackMovementRunning(now: number?): boolean
	if not attackMovementActive then
		return false
	end
	if (now or os.clock()) >= attackMovementEndsAt then
		attackMovementActive = false
		attackMovementEndsAt = 0
		if character then
			character:SetAttribute("AttackMovementActive", false)
		end
		return false
	end
	return true
end

local function baseMoveSpeedForCurrentState(targetCharacter: Model): number
	if attackMovementRunning() then
		return CharacterMovementConfig.RobloxSpeedAtRunMultiplier(
			targetCharacter:GetAttribute("CharacterArchetype"),
			targetCharacter:GetAttribute("RunSpeed"),
			attackMovementRunSpeedMultiplier
		)
	end
	return CharacterMovementConfig.RobloxSpeed(
		targetCharacter:GetAttribute("CharacterArchetype"),
		targetCharacter:GetAttribute("RunSpeed"),
		movementMode
	)
end

local function bindCharacter(newCharacter: Model)
	clearCharacter()

	local newRoot = newCharacter:WaitForChild("RootCollider", 10)
	local newNavigationRoot = newCharacter:WaitForChild("NavigationRoot", 10)
	local newManager = newCharacter:WaitForChild("ControllerManager", 10)
	if not newRoot or not newRoot:IsA("BasePart") then
		warn("[game1] RootCollider is missing")
		return
	end
	if not newNavigationRoot or not newNavigationRoot:IsA("BasePart") then
		warn("[game1] NavigationRoot is missing")
		return
	end
	if not newManager or not newManager:IsA("ControllerManager") then
		warn("[game1] ControllerManager is missing")
		return
	end

	local newGround = newManager:WaitForChild("GroundController", 10)
	local newAir = newManager:WaitForChild("AirController", 10)
	local newSensorPart = newCharacter:WaitForChild("GroundSensorPart", 10)
	local newSensor = newSensorPart and newSensorPart:WaitForChild("GroundSensor", 10)
	if not newGround or not newGround:IsA("GroundController") then
		warn("[game1] GroundController is missing")
		return
	end
	if not newAir or not newAir:IsA("AirController") then
		warn("[game1] AirController is missing")
		return
	end
	if not newSensor or not newSensor:IsA("ControllerPartSensor") then
		warn("[game1] GroundSensor is missing")
		return
	end

	if newManager.RootPart ~= newNavigationRoot then
		warn("[game1] ControllerManager.RootPart is not NavigationRoot")
		return
	end

	character = newCharacter
	root = newRoot
	navigationRoot = newNavigationRoot
	controllerManager = newManager
	groundController = newGround
	airController = newAir
	groundSensor = newSensor
	movementMode = "Run"
	movementDirectionMode = "Forward"
	newManager.BaseMoveSpeed = baseMoveSpeedForCurrentState(newCharacter)
	newCharacter:SetAttribute("AnimationMovementMode", movementMode)
	newCharacter:SetAttribute("AttackMovementActive", false)
	newCharacter:SetAttribute("AnimationMovementDirection", movementDirectionMode)
	newCharacter:SetAttribute("MovementState", "Idle")
	newCharacter:SetAttribute("MovementStateAuthority", "ClientDerivedPresentation")
	newCharacter:GetAttributeChangedSignal("RunSpeed"):Connect(function()
		if character == newCharacter and controllerManager then
			controllerManager.BaseMoveSpeed = baseMoveSpeedForCurrentState(newCharacter)
		end
	end)

	print("[game1] Custom movement bound")
end

local function inputAxis(): Vector2
	if touchMovementActive then
		return touchAxis
	end
	local x = 0
	local y = 0

	if keysDown[CharacterConfig.InputBindings.MoveLeft[1]] or keysDown[CharacterConfig.InputBindings.MoveLeft[2]] then
		x -= 1
	end
	if keysDown[CharacterConfig.InputBindings.MoveRight[1]] or keysDown[CharacterConfig.InputBindings.MoveRight[2]] then
		x += 1
	end
	if keysDown[CharacterConfig.InputBindings.MoveForward[1]] or keysDown[CharacterConfig.InputBindings.MoveForward[2]] then
		y += 1
	end
	if keysDown[CharacterConfig.InputBindings.MoveBackward[1]] or keysDown[CharacterConfig.InputBindings.MoveBackward[2]] then
		y -= 1
	end

	local axis = Vector2.new(x, y)
	if axis.Magnitude > 1 then
		axis = axis.Unit
	end
	return axis
end

local function cameraRelativeDirection(axis: Vector2): Vector3
	if axis.Magnitude <= 0 then
		return Vector3.zero
	end

	local camera = Workspace.CurrentCamera
	if not camera then
		return Vector3.zero
	end

	local look = camera.CFrame.LookVector
	local right = camera.CFrame.RightVector
	local forwardFlat = Vector3.new(look.X, 0, look.Z)
	local rightFlat = Vector3.new(right.X, 0, right.Z)

	if forwardFlat.Magnitude < 0.001 or rightFlat.Magnitude < 0.001 then
		return Vector3.zero
	end

	forwardFlat = forwardFlat.Unit
	rightFlat = rightFlat.Unit

	local direction = forwardFlat * axis.Y + rightFlat * axis.X
	if direction.Magnitude > 1 then
		direction = direction.Unit
	end
	return direction
end

local function isGrounded(): boolean
	return groundSensor ~= nil and groundSensor.SensedPart ~= nil
end

local function walkModifierDown(): boolean
	return UserInputService:IsKeyDown(CharacterConfig.InputBindings.WalkModifier[1])
		or UserInputService:IsKeyDown(CharacterConfig.InputBindings.WalkModifier[2])
end

local function isBackwardAxis(axis: Vector2): boolean
	-- S / Down selects backpedal, but only while no touch locomotion is
	-- active or a bow attack explicitly holds the facing direction.
	return axis.Y < -0.001
end

local function backwardLocomotion(axis: Vector2): boolean
	return isBackwardAxis(axis) and
		(not touchMovementActive or (aimFacingActive and aimFacingLive))
end

local function rightMouseDown(): boolean
	return UserInputService:IsMouseButtonPressed(CharacterConfig.InputBindings.CameraOrbit[1])
end

local function cameraForwardDirection(): Vector3
	local camera = Workspace.CurrentCamera
	if not camera then
		return Vector3.zero
	end

	local look = camera.CFrame.LookVector
	local forwardFlat = Vector3.new(look.X, 0, look.Z)
	if forwardFlat.Magnitude < 0.001 then
		return Vector3.zero
	end
	return forwardFlat.Unit
end

local function backwardRelativeDirection(_axis: Vector2, cameraSteering: boolean): Vector3
	if cameraSteering then
		-- RMB keeps camera-relative steering, but backpedal is constrained to one axis.
		-- A/D never add a lateral component while S is held. Camera yaw still changes
		-- the world-space backward trajectory naturally.
		return cameraRelativeDirection(Vector2.new(0, -1))
	end

	-- Without RMB, preserve classic planted backpedal relative to the character's
	-- CURRENT facing. A/D are intentionally ignored while S is held.
	local currentRoot = root
	if not currentRoot then
		return Vector3.zero
	end

	local look = currentRoot.CFrame.LookVector
	local forwardFlat = Vector3.new(look.X, 0, look.Z)
	if forwardFlat.Magnitude < 0.001 then
		return Vector3.zero
	end

	return -forwardFlat.Unit
end

local function flatUnit(direction: Vector3): Vector3?
	local flat = Vector3.new(direction.X, 0, direction.Z)
	if flat.Magnitude <= 0.001 then
		return nil
	end
	return flat.Unit
end

local function signedYaw(fromDirection: Vector3, toDirection: Vector3): number
	local from = flatUnit(fromDirection)
	local to = flatUnit(toDirection)
	if not from or not to then
		return 0
	end
	return math.atan2(from:Cross(to).Y, math.clamp(from:Dot(to), -1, 1))
end

local function rotateYaw(direction: Vector3, angle: number): Vector3
	return CFrame.fromAxisAngle(Vector3.yAxis, angle):VectorToWorldSpace(direction)
end

local function smoothStep01(value: number): number
	local t = math.clamp(value, 0, 1)
	return t * t * (3 - 2 * t)
end

local function clearAimFacingCompensation()
	aimFacingActive = false
	aimFacingLive = false
	aimFacingStartedAt = 0
	aimFacingEndsAt = 0
	aimFacingStartDirection = nil
	aimFacingTargetDirection = nil
	aimFacingMaxResidualYaw = 0
end

local function applyAimFacingCompensation(now: number, deltaTime: number, moving: boolean)
	if not aimFacingActive or not navigationRoot or not controllerManager then
		return
	end
	local startDirection = aimFacingStartDirection
	local targetDirection = aimFacingTargetDirection
	if not startDirection or not targetDirection then
		return
	end

	local facing: Vector3?
	if aimFacingLive then
		if now >= aimFacingEndsAt then
			clearAimFacingCompensation()
			return
		end
		-- While moving, ControllerManager owns physical yaw to match the gait.
		-- Bow's upper-body bridge independently follows the camera. Writing the
		-- NavigationRoot CFrame here made pelvis and legs spin with the reticle.
		if moving then return end
		local current = flatUnit(navigationRoot.CFrame.LookVector)
		if not current then return end
		-- Only turn the planted root by yaw that the spine cannot cover.
		-- Unlike the old one-shot target, this residual is updated until the
		-- complete bow animation ends, including after Release.
		local yaw = signedYaw(current, targetDirection)
		local overflow = yaw - math.clamp(yaw, -aimFacingMaxResidualYaw, aimFacingMaxResidualYaw)
		if math.abs(overflow) <= 0.0001 then return end
		local response = 4 / math.max(0.05, AttackConfig.FacingTurnSeconds)
		local blend = 1 - math.exp(-response * math.max(0, deltaTime))
		facing = flatUnit(rotateYaw(current, overflow * blend))
	else
		local duration = math.max(0.001, aimFacingEndsAt - aimFacingStartedAt)
		local alpha = smoothStep01((now - aimFacingStartedAt) / duration)
		local delta = signedYaw(startDirection, targetDirection)
		facing = flatUnit(rotateYaw(startDirection, delta * alpha))
	end
	if not facing then return end

	-- ControllerManager does not reliably rotate a completely stationary custom
	-- character just from FacingDirection. Rotate the physical NavigationRoot; the
	-- gameplay RootCollider and Visual follow through their welds without changing
	-- their vertical offsets.
	local position = navigationRoot.Position
	navigationRoot.CFrame = CFrame.lookAt(position, position + facing, Vector3.yAxis)
	controllerManager.FacingDirection = facing
end

local function applyMovementMode(walkModifierActive: boolean, backwardActive: boolean)
	-- During an attack the equipped weapon profile owns both the lower-body
	-- locomotion family and the physical movement fraction. This mirrors the
	-- RobloxLineage upper-body-over-live-locomotion contract: attacks never plant
	-- the legs unless the player actually stops moving.
	local attackActive = attackMovementRunning()
	local walkActive = walkModifierActive or backwardActive
	local nextMode = if attackActive then attackMovementMode else (walkActive and "Walk" or "Run")
	local nextDirectionMode = backwardActive and "Backward" or "Forward"
	if controllerManager and character then
		if attackActive then
			controllerManager.BaseMoveSpeed = CharacterMovementConfig.RobloxSpeedAtRunMultiplier(
				character:GetAttribute("CharacterArchetype"),
				character:GetAttribute("RunSpeed"),
				attackMovementRunSpeedMultiplier
			)
		else
			controllerManager.BaseMoveSpeed = CharacterMovementConfig.RobloxSpeed(
				character:GetAttribute("CharacterArchetype"),
				character:GetAttribute("RunSpeed"),
				nextMode
			)
		end
	end
	if character and movementMode ~= nextMode then
		movementMode = nextMode
		character:SetAttribute("AnimationMovementMode", nextMode)
	end
	if character and movementDirectionMode ~= nextDirectionMode then
		movementDirectionMode = nextDirectionMode
		character:SetAttribute("AnimationMovementDirection", nextDirectionMode)
	end
	if character then
		local movingMagnitude = if controllerManager then controllerManager.MovingDirection.Magnitude else 0
		local derivedMovement = if movingMagnitude <= 0.001 then "Idle" else nextMode
		if character:GetAttribute("MovementState") ~= derivedMovement then
			character:SetAttribute("MovementState", derivedMovement)
		end
	end
end

local function performJump()
	if not navigationRoot or not controllerManager or not airController then
		return
	end
	if not isGrounded() then
		return
	end

	controllerManager.ActiveController = airController
	jumpInFlight = true
	airLockUntil = os.clock() + CharacterConfig.JumpGroundIgnoreTime

	local upwardSpeed = navigationRoot.AssemblyLinearVelocity:Dot(Vector3.yAxis)
	local deltaVelocity = math.max(CharacterConfig.JumpVelocity * math.sqrt(JumpSettings.heightMultiplier) - upwardSpeed, 0)
	if deltaVelocity > 0 then
		navigationRoot:ApplyImpulse(Vector3.yAxis * navigationRoot.AssemblyMass * deltaVelocity)
	end
end

local function updateJumpDescent()
    local force = fallForce
    local actorRoot = navigationRoot
    if not force or not actorRoot or not character then return end
    if character:GetAttribute("LifeState") ~= "Alive" then
        force.Enabled = false
        jumpInFlight = false
        return
    end
    if isGrounded() and os.clock() >= airLockUntil then
        jumpInFlight = false
        force.Enabled = false
        return
    end
    local downward = actorRoot.AssemblyLinearVelocity.Y <= 0
    local slow = JumpSettings.descentTimeMultiplier
    local enabled = jumpInFlight and downward and math.abs(slow - 1) > 0.0001
    if enabled then
        -- Net acceleration downward is g / slow², after the jump apex.
        -- This force is positive for slow > 1, negative for slow < 1.
        force.Force = Vector3.yAxis * actorRoot.AssemblyMass * Workspace.Gravity * (1 - 1 / (slow * slow))
    end
    force.Enabled = enabled
end

local function updateMovement(deltaTime: number)
	if not character or not character.Parent then
		clearCharacter()
		return
	end
	if not root or not navigationRoot or not controllerManager or not groundController or not airController or not groundSensor then
		return
	end

	if character and tostring(character:GetAttribute("LifeState") or "Alive") ~= "Alive" then
        if fallForce then fallForce.Enabled = false end
        jumpInFlight = false
		controllerManager.MovingDirection = Vector3.zero
		if character:GetAttribute("MovementState") ~= "Idle" then
			character:SetAttribute("MovementState", "Idle")
		end
		return
	end

	if UserInputService:GetFocusedTextBox() then
		controllerManager.MovingDirection = Vector3.zero
		return
	end

	local now = os.clock()
	local axis = inputAxis()
	-- Movement remains camera-relative while the bow is firing. Lower-body
	-- facing follows travel, except on S / downward stick where it backpedals.
	local liveBowAim = aimFacingActive and aimFacingLive
	local backwardActive = backwardLocomotion(axis)
	local backwardCameraSteering = backwardActive and (rightMouseDown() or liveBowAim)
	applyMovementMode(forcedWalk or walkModifierDown(), backwardActive)
	local movementLocked = now < movementLockUntil
	local moveDirection = Vector3.zero
	if not movementLocked then
		-- Keep both keyboard and analog bow movement camera-relative, with
		-- diagonals intact. The existing one-axis S rule applies outside Bow.
		if liveBowAim then
			moveDirection = cameraRelativeDirection(axis)
		else
			moveDirection = backwardActive and backwardRelativeDirection(axis, backwardCameraSteering) or cameraRelativeDirection(axis)
		end
	end
	controllerManager.MovingDirection = moveDirection
	if aimFacingActive and not movementLocked and moveDirection.Magnitude > 0.001 then
		-- Only planted melee hands facing back to locomotion. Bow retains the
		-- reticle-facing authority even while its lower body runs or retreats.
		if not aimFacingLive then
			clearAimFacingCompensation()
		end
	end
	if movementLocked then
		jumpRequested = false
		-- Stop horizontal carry immediately and keep the attack planted in place.
		-- Preserve vertical velocity so gravity/falling still behaves normally.
		local velocity = navigationRoot.AssemblyLinearVelocity
		navigationRoot.AssemblyLinearVelocity = Vector3.new(0, velocity.Y, 0)
	end

	if liveBowAim and moveDirection.Magnitude > 0.001 then
		-- The navigation root drives pelvis + feet: never aim it at the
		-- reticle while travelling. Strafing uses the actual travel direction.
		-- Backpedal keeps the feet forward and plays the authored gait in
		-- reverse while travelling backwards (including touch diagonals).
		local lowerBodyFacing = if backwardActive then cameraForwardDirection() else moveDirection
		if lowerBodyFacing.Magnitude > 0.001 then
			controllerManager.FacingDirection = lowerBodyFacing
		end
	elseif facingLockDirection and now < facingLockUntil then
		-- Original melee facing lock. Camera orbit remains owned
		-- exclusively by CameraController, irrespective of the equipped weapon.
		controllerManager.FacingDirection = facingLockDirection
	else
		if facingLockDirection then
			facingLockDirection = nil
			facingLockUntil = 0
		end
		if moveDirection.Magnitude > 0.001 then
			if not backwardActive then
				-- Moving players face travel, as they do with hands equipped.
				controllerManager.FacingDirection = moveDirection
			elseif backwardCameraSteering then
				-- RMB + S backpedal: steer with camera while travelling backwards.
				local cameraForward = cameraForwardDirection()
				if cameraForward.Magnitude > 0.001 then
					controllerManager.FacingDirection = cameraForward
				end
			end
			-- Without RMB, backpedal preserves the current facing.
		end
	end
	-- Only a planted bow may rotate the physical root for spine overflow.
	-- Locomotion must never be overwritten by the aim compensation layer.
	applyAimFacingCompensation(now, deltaTime, moveDirection.Magnitude > 0.001)

	if now >= airLockUntil then
		if isGrounded() then
			controllerManager.ActiveController = groundController
		else
			controllerManager.ActiveController = airController
		end
	end

	if jumpRequested then
		jumpRequested = false
		if not movementLocked then
			performJump()
		end
	end
	updateJumpDescent()
end

function MovementController.SetTouchMovement(axis: Vector2, active: boolean)
	-- A finger owns the movement input until release, even at the stick's neutral point.
	touchMovementActive = active == true
	if not touchMovementActive then
		touchAxis = Vector2.zero
	else
		local magnitude = axis.Magnitude
		touchAxis = if magnitude > 1 then axis.Unit else axis
	end
end

function MovementController.RequestJump()
	-- Same jump path as Space; grounding and attack locks are checked in updateMovement.
	if not UserInputService:GetFocusedTextBox() then
		jumpRequested = true
	end
end

function MovementController.IsMoving(): boolean
	if movementLockUntil > os.clock() then
		return false
	end
	return inputAxis().Magnitude > 0.001
end

function MovementController.BeginAttackMovement(weaponType: any, duration: number): any
	local resolved = WeaponAttackMovement.Resolve(weaponType)
	attackMovementActive = true
	attackMovementEndsAt = os.clock() + math.max(0.05, tonumber(duration) or 0.05)
	attackMovementMode = tostring(resolved.locomotionMode or "Run")
	attackMovementRunSpeedMultiplier = math.clamp(tonumber(resolved.runSpeedMultiplier) or 1, 0, 2)
	if character then
		character:SetAttribute("AttackMovementActive", true)
		character:SetAttribute("AttackMovementLocomotionMode", attackMovementMode)
		character:SetAttribute("AttackMovementRunSpeedMultiplier", attackMovementRunSpeedMultiplier)
	end
	if controllerManager and character then
		local axis = inputAxis()
		applyMovementMode(walkModifierDown(), backwardLocomotion(axis))
	end
	return resolved
end

function MovementController.EndAttackMovement()
	attackMovementActive = false
	attackMovementEndsAt = 0
	if character then
		character:SetAttribute("AttackMovementActive", false)
	end
	if controllerManager and character then
		local axis = inputAxis()
		applyMovementMode(forcedWalk or walkModifierDown(), backwardLocomotion(axis))
	end
end

function MovementController.BeginForcedWalk()
	forcedWalk = true
	if controllerManager and character then
		applyMovementMode(true, false)
	end
end

function MovementController.EndForcedWalk()
	forcedWalk = false
	if controllerManager and character then
		local axis = inputAxis()
		applyMovementMode(walkModifierDown(), backwardLocomotion(axis))
	end
end

function MovementController.LockMovement(duration: number)
	movementLockUntil = math.max(movementLockUntil, os.clock() + math.max(0.05, tonumber(duration) or 0.05))
	jumpRequested = false
	if controllerManager then
		controllerManager.MovingDirection = Vector3.zero
	end
	if navigationRoot then
		local velocity = navigationRoot.AssemblyLinearVelocity
		navigationRoot.AssemblyLinearVelocity = Vector3.new(0, velocity.Y, 0)
	end
end

function MovementController.UnlockMovement()
	movementLockUntil = 0
end

function MovementController.LockFacing(direction: Vector3, duration: number)
	local flat = Vector3.new(direction.X, 0, direction.Z)
	if flat.Magnitude <= 0.001 then
		return
	end
	facingLockDirection = flat.Unit
	facingLockUntil = os.clock() + math.max(0.05, tonumber(duration) or 0.05)
	if controllerManager then
		controllerManager.FacingDirection = facingLockDirection
	end
end

function MovementController.UnlockFacing()
	facingLockDirection = nil
	facingLockUntil = 0
end

function MovementController.BeginAimFacingCompensation(duration: number, maxResidualYaw: number, live: boolean?)
	if not root then
		return false
	end
	local startDirection = flatUnit(root.CFrame.LookVector)
	if not startDirection then
		return false
	end
	local now = os.clock()
	aimFacingActive = true
	aimFacingLive = live == true
	aimFacingStartedAt = now
	aimFacingEndsAt = now + math.max(0.05, tonumber(duration) or 0.05)
	aimFacingStartDirection = startDirection
	aimFacingTargetDirection = startDirection
	aimFacingMaxResidualYaw = math.max(0, tonumber(maxResidualYaw) or 0)
	return true
end

function MovementController.UpdateAimFacingCompensation(aimDirection: Vector3)
	if not aimFacingActive then
		return false
	end
	local aim = flatUnit(aimDirection)
	if not aim then return false end
	if aimFacingLive then
		-- Keep the live camera target for the torso. Physical root compensation
		-- happens only if planted and only beyond the allowable torso yaw.
		aimFacingTargetDirection = aim
		return true
	end
	local startDirection = aimFacingStartDirection
	if not startDirection then return false end

	-- Planted melee retains M314's initial root overflow split. Example:
	-- 150° aim with 70° torso limit => root turns 80° and torso holds 70°.
	local fullYaw = signedYaw(startDirection, aim)
	local torsoYaw = math.clamp(fullYaw, -aimFacingMaxResidualYaw, aimFacingMaxResidualYaw)
	local rootYaw = fullYaw - torsoYaw
	aimFacingTargetDirection = flatUnit(rotateYaw(startDirection, rootYaw)) or startDirection
	return true
end

function MovementController.EndAimFacingCompensation()
	clearAimFacingCompensation()
end

function MovementController.IsAimFacingCompensationActive(): boolean
	return aimFacingActive
end

function MovementController.Start()
	if started then
		return
	end
	started = true

	UserInputService.InputBegan:Connect(function(input: InputObject, gameProcessed: boolean)
		if UiInputGuard.BlocksWorldInput(input, gameProcessed) then
			return
		end

		if input.UserInputType == Enum.UserInputType.Keyboard then
			keysDown[input.KeyCode] = true
			if input.KeyCode == CharacterConfig.InputBindings.Jump[1] then
				MovementController.RequestJump()
			end
		end
	end)

	UserInputService.InputEnded:Connect(function(input: InputObject)
		if input.UserInputType == Enum.UserInputType.Keyboard then
			keysDown[input.KeyCode] = nil
		end
	end)

	localPlayer.CharacterAdded:Connect(bindCharacter)
	localPlayer.CharacterRemoving:Connect(function(removingCharacter)
		if removingCharacter == character then
			clearCharacter()
		end
	end)

	if localPlayer.Character then
		task.spawn(bindCharacter, localPlayer.Character)
	end

	RunService.PreSimulation:Connect(updateMovement)
end

return MovementController

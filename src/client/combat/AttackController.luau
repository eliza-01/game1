local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local CharacterAttackHitEnd = require(CombatShared:WaitForChild("CharacterAttackHitEnd"))
local BowProjectileConfig = require(CombatShared:WaitForChild("BowProjectileConfig"))
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local BoneMountedAttachmentController = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("BoneMountedAttachmentController"))
local AttackController = {}
local started = false
local movementController: any = nil
local animationController: any = nil
local aimPoseController: any = nil
local attackSequence = 0
local activeMeleeAimId = 0
local bowCaptureSequence = 0
local bowPresentationUntil = 0
local bowPresentationCharacter: Model? = nil
local meleePresentationSequence = 0
local meleePresentationUntil = 0
local meleePresentationCharacter: Model? = nil
local meleeHitEndAt = 0
local nextMeleeAimAt = 0
-- Gameplay aim packets are bounded; visual camera tracking remains every frame.
local MELEE_AIM_SEND_INTERVAL = 0.10
local meleeAimRemote: RemoteEvent? = nil
local bowAimRemote: RemoteEvent? = nil


-- Only client camera AIM is shared for an optional headshot classification.
-- Never send a weapon mesh transform, collision box, reach or target list.
local function publishMeleeAim()
    if not meleeAimRemote or activeMeleeAimId <= 0 then return end
    local character = Players.LocalPlayer.Character
    if not character or character:GetAttribute("LifeState") ~= "Alive" then return end
    if not aimPoseController or not aimPoseController.GetAimRay then return end
    local origin, direction = aimPoseController.GetAimRay()
    if typeof(origin) ~= "Vector3" or typeof(direction) ~= "Vector3" then return end
    meleeAimRemote:FireServer({
        clientAttackId = activeMeleeAimId,
        aimOrigin = origin,
        aimDirection = direction,
    })
end

local function finishPresentation(sequence: number)
    if sequence ~= attackSequence then
        return
    end
    if movementController then
        if movementController.EndAimFacingCompensation then
            movementController.EndAimFacingCompensation()
        end
        if movementController.UnlockFacing then
            movementController.UnlockFacing()
        end
        if movementController.EndAttackMovement then
            movementController.EndAttackMovement()
        end
    end
    bowCaptureSequence = 0
    bowPresentationUntil = 0
    bowPresentationCharacter = nil
    meleePresentationSequence = 0
    meleePresentationUntil = 0
    meleePresentationCharacter = nil
    meleeHitEndAt = 0
    nextMeleeAimAt = 0
    if activeMeleeAimId == sequence then
        activeMeleeAimId = 0
    end
    if aimPoseController and aimPoseController.EndAttack then
        aimPoseController.EndAttack()
    end
end

function AttackController.CancelForBounce(clientAttackId: number)
    local id = math.floor(tonumber(clientAttackId) or 0)
    if id <= 0 or id ~= attackSequence then
        return false
    end
    if activeMeleeAimId == id then
        activeMeleeAimId = 0
    end
    finishPresentation(id)
    return true
end

function AttackController.Start(movement: any?, animation: any?, aimPose: any?)
    movementController = movement
    animationController = animation
    aimPoseController = aimPose
    if started then return end
    started = true
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    local attack = remotes:WaitForChild("AttackIntent")
    meleeAimRemote = remotes:WaitForChild("MeleeAimUpdate") :: RemoteEvent
    bowAimRemote = remotes:WaitForChild("BowAimUpdate") :: RemoteEvent

    RunService.RenderStepped:Connect(function(_deltaTime)
        -- Both weapon types track the live camera through the COMPLETE clip.
        -- Bow still captures one authoritative Release snapshot; melee updates
        -- bounded camera AIM packets until HitEnd, never hitboxes or damage.
        local isBowPresentation = bowCaptureSequence > 0
        local sequence = if isBowPresentation then bowCaptureSequence else meleePresentationSequence
        if sequence <= 0 then return end
        local expectedCharacter = if isBowPresentation then bowPresentationCharacter else meleePresentationCharacter
        local presentationUntil = if isBowPresentation then bowPresentationUntil else meleePresentationUntil
        local playerCharacter = Players.LocalPlayer.Character
        local now = os.clock()
        if playerCharacter ~= expectedCharacter
            or not playerCharacter or playerCharacter:GetAttribute("LifeState") ~= "Alive"
            or now > presentationUntil then
            finishPresentation(sequence)
            return
        end
        if not aimPoseController or not movementController then return end
        local origin, direction = aimPoseController.GetAimRay()
        if typeof(origin) ~= "Vector3" or typeof(direction) ~= "Vector3"
            or direction.Magnitude <= 1e-6 then return end
        local target = origin + direction.Unit * AttackConfig.MaxAimDistance
        aimPoseController.UpdateTarget(target, direction)
        local root = playerCharacter:FindFirstChild("RootCollider")
        if root and root:IsA("BasePart") then
            movementController.UpdateAimFacingCompensation(target - root.Position)
        end
        -- The server still resolves a SINGLE contact at authored HitEnd.
        -- Send only a recent heading, not a client-selected hit result.
        if not isBowPresentation and activeMeleeAimId == sequence
            and now <= meleeHitEndAt and now >= nextMeleeAimAt then
            publishMeleeAim()
            nextMeleeAimAt = now + MELEE_AIM_SEND_INTERVAL
        end
    end)
    local function attemptAttack()
        if UiInputGuard.IsWorldSuspended() then return end
        local player = Players.LocalPlayer
        local character = player.Character
        if not character or tostring(character:GetAttribute("LifeState") or "Alive") ~= "Alive" then
            return
        end

        if character:GetAttribute("SkillStunned") == true then return end
        if not animationController then return end
        local isBow = string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow"
        -- Bow facing starts with Draw, not with the late target snapshot.
        -- This ray is already used by AttackIntent: no additional world raycast
        -- or per-frame target tracking is needed before Release.
        local bowAimOrigin, bowAimDirection = nil, nil
        if isBow then
            if not aimPoseController or not aimPoseController.GetAimRay then return end
            bowAimOrigin, bowAimDirection = aimPoseController.GetAimRay()
            if typeof(bowAimOrigin) ~= "Vector3" or typeof(bowAimDirection) ~= "Vector3"
                or bowAimDirection.Magnitude <= 1e-6 then return end
        end
        -- Every attack begins from the actual reticle RAY, not a near hit point.
        -- This avoids turning the torso away when a close target crosses camera.
        local initialAimOrigin, initialAimDirection = bowAimOrigin, bowAimDirection
        if not isBow then
            if not aimPoseController or not aimPoseController.GetAimRay then return end
            initialAimOrigin, initialAimDirection = aimPoseController.GetAimRay()
            if typeof(initialAimOrigin) ~= "Vector3" or typeof(initialAimDirection) ~= "Vector3"
                or initialAimDirection.Magnitude <= 1e-6 then return end
        end

        -- PlayAction owns the complete attack interval. It returns nil while the
        -- previous attack animation is still inside its configured timeline, so
        -- repeated input can never cut an attack short.
        local action = animationController.PlayAction("attack")
        if not action then
            return
        end

        local release = isBow and action.timeline and action.timeline.events
            and action.timeline.events[BowProjectileConfig.ReleaseEvent] or nil
        local hitEndEvent = if isBow then nil else CharacterAttackHitEnd.Resolve(action.timeline)
        if (isBow and not release) or (not isBow and not hitEndEvent) then
            warn(("[game1][attack] missing %s event(s): %s"):format(
                if isBow then "Release" else "HitEnd", tostring(action.clipId)))
            return
        end

        attackSequence += 1
        local sequence = attackSequence
        local attackDuration = math.max(0.05, tonumber(action.durationSeconds) or 0.05)
        local damagePoseStart = math.clamp(if isBow then release.time else hitEndEvent.time, 0, attackDuration)
        if movementController and movementController.BeginAttackMovement then
            -- Every weapon may attack while moving. The equipped weapon type
            -- resolves an authored lower-body gait + RunSpeed fraction; no
            -- weapon-specific numbers live in this controller.
            movementController.BeginAttackMovement(character:GetAttribute("EquippedWeaponType"), attackDuration)
        end

        local root = character:FindFirstChild("RootCollider")
        -- Face the reticle immediately for Bow and Melee alike. Bow uses its
        -- initial camera direction only to drive presentation; the authoritative
        -- target is still captured just once close to Release.
        local presentationTarget = initialAimOrigin + initialAimDirection.Unit * AttackConfig.MaxAimDistance
        if root and root:IsA("BasePart") then
            local direction = Vector3.new(presentationTarget.X - root.Position.X, 0,
                presentationTarget.Z - root.Position.Z)
            if direction.Magnitude > 0.001 then
                -- Facing is a gameplay interval, not a function of the FBX clip's
                -- individual playback multiplier.
                if isBow and movementController and movementController.BeginAimFacingCompensation then
                    -- Bow tracks the reticle while idle, moving and backpedalling.
                    -- Moving feet follow travel; only the spine follows the aim.
                    -- A planted root rotates by the residual outside torso yaw.
                    movementController.BeginAimFacingCompensation(
                        attackDuration, AttackConfig.TorsoYawLimit, true
                    )
                    movementController.UpdateAimFacingCompensation(direction.Unit)
                elseif not isBow and movementController then
                    -- During a sword swing the lower body stays on the same
                    -- travel-facing path as Bow. At rest only the residual yaw
                    -- beyond the upper-body allowance turns the physical root.
                    -- The server independently clamps the saved camera heading
                    -- before its one authoritative HitEnd contact query.
                    if movementController.BeginAimFacingCompensation then
                        movementController.BeginAimFacingCompensation(
                            attackDuration,
                            movementController.MeleeMaxResidualYaw(), true
                        )
                        movementController.UpdateAimFacingCompensation(direction.Unit)
                    else
                        movementController.LockFacing(direction.Unit, attackDuration)
                    end
                end
            end
        end
        if aimPoseController then
            -- The same torso controller applies both weapon types. The bow's
            -- cosmetic target follows the camera; Capture never changes it.
            aimPoseController.BeginAttack(presentationTarget, attackDuration)
        end


        task.delay(attackDuration, function()
            finishPresentation(sequence)
        end)

        -- The server schedules Release. The initial camera direction is only
        -- validated as an attack request; it is NOT a captured hit or target.
        if isBow then
            attack:FireServer({
                clipId = action.clipId,
                clientAttackId = sequence,
                aimOrigin = bowAimOrigin,
                aimDirection = bowAimDirection,
            })
            -- Exactly one late capture for SERVER damage. Presentation tracks
            -- the CAMERA ray each render frame without raycasts or remotes.
            bowCaptureSequence = sequence
            bowPresentationUntil = os.clock() + attackDuration
            bowPresentationCharacter = character
            local lead = math.min(BowProjectileConfig.CaptureLeadSeconds, damagePoseStart * 0.5)
            task.delay(math.max(0.025, damagePoseStart - lead), function()
                if sequence ~= bowCaptureSequence or sequence ~= attackSequence or player.Character ~= character
                    or character:GetAttribute("LifeState") ~= "Alive" then return end
                local origin, direction = aimPoseController.GetAimRay()
                if not origin or not direction then return end
                local launchOrigin = BoneMountedAttachmentController.GetBowReleaseOrigin(character)
                bowAimRemote:FireServer({
                    clientAttackId = sequence,
                    aimOrigin = origin,
                    aimDirection = direction,
                    launchOrigin = launchOrigin,
                })
                -- Capture is gameplay-only. Never snap the torso to a close
                -- surface at Release: the live camera ray still owns the pose.
            end)
            return
        end

        -- Visual tracking persists until the final attack frame. Gameplay
        -- updates are limited to the pre-HitEnd interval and rate capped.
        meleePresentationSequence = sequence
        meleePresentationUntil = os.clock() + attackDuration
        meleePresentationCharacter = character
        meleeHitEndAt = os.clock() + hitEndEvent.time
        nextMeleeAimAt = 0
        activeMeleeAimId = sequence
        local lead = math.min(AttackConfig.MeleeAimCaptureLeadSeconds, hitEndEvent.time * 0.5)
        task.delay(math.max(0, hitEndEvent.time - lead), function()
            if sequence ~= attackSequence or activeMeleeAimId ~= sequence
                or player.Character ~= character or character:GetAttribute("LifeState") ~= "Alive" then return end
            publishMeleeAim()
            activeMeleeAimId = 0
        end)
        attack:FireServer({
            clipId = action.clipId,
            clientAttackId = sequence,
            aimOrigin = initialAimOrigin,
            aimDirection = initialAimDirection,
        })
    end

    AttackController.RequestAttack = attemptAttack
    UserInputService.InputBegan:Connect(function(input, processed)
        if input.UserInputType == CharacterConfig.InputBindings.AttackPrimary[1]
            and not UiInputGuard.BlocksWorldInput(input, processed) then
            attemptAttack()
        end
    end)
end
return AttackController

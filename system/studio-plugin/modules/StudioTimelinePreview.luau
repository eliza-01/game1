-- Owns the isolated ViewportFrame rig, camera interaction and animation-asset retrieval.
local StudioTimelinePreview = {}
local StudioCharacterStandBuilder = require(script.Parent.StudioCharacterStandBuilder)

function StudioTimelinePreview.new(services)
    local AssetService = services.AssetService
    local AnimationClipProvider = services.AnimationClipProvider
    local UserInputService = services.UserInputService
    local timelineViewport = services.viewport
    local timelineWorld = services.world
    local timelineCamera = services.camera
    local timelineViewportEmpty = services.empty
    local TIMELINE_PREVIEW_NAME = "Game1TimelinePreview"
    local activePreview: Model? = nil
    local timelinePreviewDragging = false
    local timelineCameraTarget = Vector3.zero
    local timelineCameraYaw = math.pi
    local timelineCameraPitch = 0
    local timelineCameraDistance = 8
    local timelineCameraMinDistance = 2
    local timelineCameraMaxDistance = 24

    local function updateTimelinePreviewCamera()
        timelineCameraDistance = math.clamp(timelineCameraDistance, timelineCameraMinDistance, timelineCameraMaxDistance)
        timelineCameraPitch = math.clamp(timelineCameraPitch, math.rad(-70), math.rad(70))
        local cosPitch = math.cos(timelineCameraPitch)
        local offset = Vector3.new(
            math.sin(timelineCameraYaw) * cosPitch,
            math.sin(timelineCameraPitch),
            math.cos(timelineCameraYaw) * cosPitch
        ) * timelineCameraDistance
        timelineCamera.CFrame = CFrame.lookAt(timelineCameraTarget + offset, timelineCameraTarget, Vector3.yAxis)
    end

    local function frameTimelinePreview(preview: Model)
        preview:PivotTo(CFrame.new())
        local boundsCFrame, boundsSize = preview:GetBoundingBox()
        local radius = math.max(boundsSize.X, boundsSize.Y, boundsSize.Z, 1)
        local rootPart = preview:FindFirstChild("RootPart", true)
            or preview:FindFirstChild("HumanoidRootPart", true)
            or preview:FindFirstChildWhichIsA("BasePart", true)
        local front = Vector3.new(0, 0, -1)
        if rootPart and rootPart:IsA("BasePart") then
            front = rootPart.CFrame.LookVector
        end
        local horizontalFront = Vector3.new(front.X, 0, front.Z)
        if horizontalFront.Magnitude < 0.01 then
            horizontalFront = Vector3.new(0, 0, -1)
        else
            horizontalFront = horizontalFront.Unit
        end
        timelineCameraTarget = boundsCFrame.Position + Vector3.new(0, boundsSize.Y * 0.02, 0)
        timelineCameraMinDistance = math.max(radius * 0.55, 0.75)
        timelineCameraMaxDistance = math.max(radius * 4.5, timelineCameraMinDistance + 1)
        local initialOffset = horizontalFront * radius * 1.8 + Vector3.new(0, boundsSize.Y * 0.03, 0)
        timelineCameraDistance = math.clamp(initialOffset.Magnitude, timelineCameraMinDistance, timelineCameraMaxDistance)
        if initialOffset.Magnitude > 0.001 then
            timelineCameraYaw = math.atan2(initialOffset.X, initialOffset.Z)
            timelineCameraPitch = math.asin(math.clamp(initialOffset.Y / initialOffset.Magnitude, -1, 1))
        else
            timelineCameraYaw = math.pi
            timelineCameraPitch = 0
        end
        updateTimelinePreviewCamera()
    end

    timelineViewport.InputBegan:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 and activePreview ~= nil then
            timelinePreviewDragging = true
        end
    end)

    timelineViewport.InputChanged:Connect(function(input)
        if activePreview == nil then
            return
        end
        if input.UserInputType == Enum.UserInputType.MouseMovement and timelinePreviewDragging then
            timelineCameraYaw -= input.Delta.X * 0.010
            timelineCameraPitch = math.clamp(timelineCameraPitch - input.Delta.Y * 0.008, math.rad(-70), math.rad(70))
            updateTimelinePreviewCamera()
        elseif input.UserInputType == Enum.UserInputType.MouseWheel then
            local wheel = input.Position.Z
            if math.abs(wheel) > 0.001 then
                local step = math.max(timelineCameraDistance * 0.12, 0.15)
                timelineCameraDistance = math.clamp(
                    timelineCameraDistance - wheel * step,
                    timelineCameraMinDistance,
                    timelineCameraMaxDistance
                )
                updateTimelinePreviewCamera()
            end
        end
    end)

    timelineViewport.InputEnded:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 then
            timelinePreviewDragging = false
        end
    end)


        UserInputService.InputEnded:Connect(function(input)
            if input.UserInputType == Enum.UserInputType.MouseButton1 then
                timelinePreviewDragging = false
            end
        end)

    local function destroyTimelinePreview()
        if activePreview ~= nil then
            pcall(function()
                activePreview:Destroy()
            end)
            activePreview = nil
        end
        for _, child in ipairs(timelineWorld:GetChildren()) do
            child:Destroy()
        end
        timelineViewportEmpty.Visible = true
    end

    local function prepareTimelinePreviewModel(preview: Model)
        for _, descendant in ipairs(preview:GetDescendants()) do
            if descendant:IsA("BasePart") then
                descendant.Anchored = true
                descendant.CanCollide = false
                descendant.CanTouch = false
                descendant.CanQuery = false
                descendant.Massless = true
            elseif descendant:IsA("Script") or descendant:IsA("LocalScript") then
                descendant:Destroy()
            end
        end
    end

    local function loadTimelinePreviewModel(assetId: number): Model
        local loaded: Instance? = nil
        local lastError = ""
        for _ = 1, 6 do
            local loadedOk, value = pcall(function()
                return AssetService:LoadAssetAsync(assetId)
            end)
            if loadedOk and value ~= nil then
                loaded = value
                break
            end
            lastError = tostring(value)
            task.wait(0.5)
        end
        if loaded == nil then
            error("could not load preview model asset " .. tostring(assetId) .. ": " .. lastError)
        end

        local imported: Instance = loaded
        local children = loaded:GetChildren()
        if loaded:IsA("Model") and #children == 1 then
            imported = children[1]
            imported.Parent = nil
            loaded:Destroy()
        end

        local preview = Instance.new("Model")
        preview.Name = TIMELINE_PREVIEW_NAME
        preview:SetAttribute("Game1TimelinePreview", true)
        imported.Name = "ImportedRig"
        imported.Parent = preview
        prepareTimelinePreviewModel(preview)
        preview.Parent = timelineWorld
        frameTimelinePreview(preview)
        timelineViewportEmpty.Visible = false
        activePreview = preview
        return preview
    end

    -- Preview Studio Play's actual admin assembly (rig + parts + materials),
    -- never the invisible rig-only Model. The build uses the shared server
    -- CharacterAssemblyBuilder through StudioCharacterStandBuilder.
    local function loadTimelineAdminModel(characterId: string): Model
        local profile = StudioCharacterStandBuilder.AdminProfile(characterId)
        local preview = StudioCharacterStandBuilder.Build(AssetService, profile)
        preview.Name = TIMELINE_PREVIEW_NAME
        preview:SetAttribute("Game1TimelinePreview", true)
        local visible = 0
        for _, descendant in ipairs(preview:GetDescendants()) do
            if descendant:IsA("MeshPart") and descendant.Transparency < 0.99 then
                visible += 1
            end
        end
        if visible == 0 then
            preview:Destroy()
            error("Studio admin assembly contains no visible MeshParts; check published components")
        end
        prepareTimelinePreviewModel(preview)
        preview.Parent = timelineWorld
        frameTimelinePreview(preview)
        timelineViewportEmpty.Visible = false
        activePreview = preview
        return preview
    end

    local hairFollower = nil
    local function refreshTimelineAccessories(preview: Model)
        -- The same HairAttachmentController that positions pivot hair in Play,
        -- called once per scrubbed pose instead of starting a render loop.
        if hairFollower == nil then
            local scripts = game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
            local client = scripts and scripts:FindFirstChild("Game1Client")
            local character = client and client:FindFirstChild("character")
            local source = character and character:FindFirstChild("HairAttachmentController")
            if source and source:IsA("ModuleScript") then
                hairFollower = require(source)
            else
                return -- The preview remains usable without optional pivot hair.
            end
        end
        if hairFollower.UpdateCharacter then hairFollower.UpdateCharacter(preview) end
    end

    -- AnimationClipProvider can transiently return an empty KeyframeSequence for a
    -- published animation. Do not mistake that response for an authored 0-second
    -- attack, and never invent keyframes or infer them from timeline metadata.
    local MAX_CLIP_FETCHES = 5
    local CLIP_RETRY_SECONDS = 0.4

    local function timelineSequenceDetails(sequence: KeyframeSequence): (number, number, number)
        local duration = 0
        local keyframeCount = 0
        local poseCount = 0
        for _, keyframe in ipairs(sequence:GetKeyframes()) do
            keyframeCount += 1
            duration = math.max(duration, keyframe.Time)
            for _, descendant in ipairs(keyframe:GetDescendants()) do
                if descendant:IsA("Pose") then
                    poseCount += 1
                end
            end
        end
        return duration, keyframeCount, poseCount
    end

    local function loadTimelineSequence(animationAssetId: number): KeyframeSequence
        local contentId = "rbxassetid://" .. tostring(math.floor(animationAssetId))
        local lastDiagnostic = "no response"
        for attempt = 1, MAX_CLIP_FETCHES do
            local ok, clip = pcall(function()
                return AnimationClipProvider:GetAnimationClipAsync(contentId)
            end)
            if ok and clip ~= nil then
                if not clip:IsA("KeyframeSequence") then
                    local clipClass = clip.ClassName
                    clip:Destroy()
                    -- CurveAnimations need a curve sampler; they are not empty
                    -- KeyframeSequences and must not be silently misdiagnosed.
                    error(("animation %d is %s, not KeyframeSequence; the timeline pose preview does not yet support this clip format")
                        :format(animationAssetId, clipClass))
                end
                local duration, frameCount, poseCount = timelineSequenceDetails(clip)
                if duration > 0.000001 and poseCount > 0 then
                    return clip
                end
                lastDiagnostic = ("keyframes=%d, poses=%d, last keyframe=%.6fs, loaded length=%.6fs")
                    :format(frameCount, poseCount, duration, clip.Length)
                clip:Destroy()
            else
                lastDiagnostic = "request failed: " .. tostring(clip)
            end
            if attempt < MAX_CLIP_FETCHES then
                task.wait(CLIP_RETRY_SECONDS)
            end
        end
        error(("published animation %d has no usable timed poses after %d Studio requests (%s). "
            .. "Verify the published clip's keys in Roblox Animation Editor. No hit events were changed.")
            :format(animationAssetId, MAX_CLIP_FETCHES, lastDiagnostic))
    end

    local function timelineSequenceDuration(sequence: KeyframeSequence): number
        local duration = timelineSequenceDetails(sequence)
        return duration
    end


    return {
        DestroyPreview = destroyTimelinePreview,
        LoadModel = loadTimelinePreviewModel,
        LoadAdminModel = loadTimelineAdminModel,
        RefreshAccessories = refreshTimelineAccessories,
        LoadSequence = loadTimelineSequence,
        SequenceDuration = timelineSequenceDuration,
    }
end

return table.freeze(StudioTimelinePreview)

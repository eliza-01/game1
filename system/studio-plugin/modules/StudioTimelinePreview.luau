-- Owns the isolated ViewportFrame rig, camera interaction and animation-asset retrieval.
local StudioTimelinePreview = {}

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

    local function loadTimelineSequence(animationAssetId: number): KeyframeSequence
        local contentId = "rbxassetid://" .. tostring(math.floor(animationAssetId))
        local lastError = ""
        for _ = 1, 4 do
            local ok, clip = pcall(function()
                return AnimationClipProvider:GetAnimationClipAsync(contentId)
            end)
            if ok and clip ~= nil then
                if not clip:IsA("KeyframeSequence") then
                    clip:Destroy()
                    error("Attack Timeline requires a KeyframeSequence animation asset")
                end
                return clip
            end
            lastError = tostring(clip)
            task.wait(0.4)
        end
        error("could not load animation clip " .. tostring(animationAssetId) .. ": " .. lastError)
    end

    local function timelineSequenceDuration(sequence: KeyframeSequence): number
        local duration = 0
        for _, keyframe in ipairs(sequence:GetKeyframes()) do
            duration = math.max(duration, keyframe.Time)
        end
        return duration
    end


    return {
        DestroyPreview = destroyTimelinePreview,
        LoadModel = loadTimelinePreviewModel,
        LoadSequence = loadTimelineSequence,
        SequenceDuration = timelineSequenceDuration,
    }
end

return table.freeze(StudioTimelinePreview)

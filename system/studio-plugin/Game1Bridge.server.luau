local AnimationClipProvider = game:GetService("AnimationClipProvider")
local AssetService = game:GetService("AssetService")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local Selection = game:GetService("Selection")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local LocationCommands = require(script.Parent.modules.LocationCommands)
local StudioMarkerVisibility = require(script.Parent.modules.StudioMarkerVisibility)
local StudioDebugPreferenceBridge = require(script.Parent.modules.StudioDebugPreferenceBridge)
local StudioModelLoadCommands = require(script.Parent.modules.StudioModelLoadCommands)
local StudioActorSpawnCommands = require(script.Parent.modules.StudioActorSpawnCommands)
local DecoManager = require(script.Parent.modules.DecoManager)

local toolbar = plugin:CreateToolbar("game1")
local markerVisibility = StudioMarkerVisibility.new(plugin, toolbar, Workspace)
local AGENT_BASE_URL = "http://127.0.0.1:43821"
local AGENT_URL = AGENT_BASE_URL .. "/api/agent/info"
local AGENT_TOKEN = "Game1LocalControlV1"
local BRIDGE_URL = "http://127.0.0.1:43137"
local BRIDGE_TOKEN = "Game1StudioBridgeV1"

local locationCommands = LocationCommands({
    HttpService = HttpService,
    Selection = Selection,
    Workspace = Workspace,
    UserInputService = UserInputService,
    BRIDGE_URL = BRIDGE_URL,
    BRIDGE_TOKEN = BRIDGE_TOKEN,
    plugin = plugin,
})

local decoManager = DecoManager.new({
    plugin = plugin,
    toolbar = toolbar,
    HttpService = HttpService,
    AssetService = AssetService,
    Workspace = Workspace,
    ChangeHistoryService = ChangeHistoryService,
    UserInputService = UserInputService,
    agentBaseUrl = AGENT_BASE_URL,
    agentToken = AGENT_TOKEN,
})

StudioDebugPreferenceBridge({
    plugin = plugin,
    ReplicatedStorage = ReplicatedStorage,
    RunService = RunService,
})

local function checkAgent()
    local ok, response = pcall(HttpService.RequestAsync, HttpService, {
        Url = AGENT_URL,
        Method = "GET",
        Headers = { ["X-Control-Token"] = AGENT_TOKEN },
    })
    if not ok then
        warn("[game1 plugin] control center agent is unavailable: " .. tostring(response))
        return
    end
    if not response.Success then
        warn(("[game1 plugin] agent http %d: %s"):format(response.StatusCode, response.Body))
        return
    end
    local decodedOk, data = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if decodedOk then
        print(("[game1 plugin] connected · %s · %s"):format(tostring(data.project), tostring(data.build)))
    else
        print("[game1 plugin] connected")
    end
end


local handleModelLoad = StudioModelLoadCommands({
    AssetService = AssetService,
    HttpService = HttpService,
    ServerStorage = ServerStorage,
    bridgeUrl = BRIDGE_URL,
    bridgeToken = BRIDGE_TOKEN,
})

local handleMonsterSpawn = StudioActorSpawnCommands({
    plugin = plugin,
    HttpService = HttpService,
    Selection = Selection,
    ServerStorage = ServerStorage,
    UserInputService = UserInputService,
    Workspace = Workspace,
    bridgeUrl = BRIDGE_URL,
    bridgeToken = BRIDGE_TOKEN,
})

local TIMELINE_PREVIEW_NAME = "Game1TimelinePreview"
local timelineWidgetInfo = DockWidgetPluginGuiInfo.new(
    Enum.InitialDockState.Right,
    false,
    false,
    560,
    640,
    440,
    620
)
local timelineWidget = plugin:CreateDockWidgetPluginGui("Game1AttackTimeline_v2", timelineWidgetInfo)
timelineWidget.Title = "game1 · Attack Timeline"

local timelineEditor = {
    sessionId = "",
    clipId = "",
    clipName = "",
    subjectName = "",
    duration = 0,
    normalized = 0,
    selectedEvent = "Hit",
    eventCatalog = {},
    events = {},
    poseTracks = {},
    preview = nil,
}
local timelineDragging = false
local timelinePreviewDragging = false
local timelineCameraTarget = Vector3.zero
local timelineCameraYaw = math.pi
local timelineCameraPitch = 0
local timelineCameraDistance = 8
local timelineCameraMinDistance = 2
local timelineCameraMaxDistance = 24

local timelineRoot = Instance.new("Frame")
timelineRoot.Name = "Root"
timelineRoot.BackgroundColor3 = Color3.fromRGB(32, 34, 39)
timelineRoot.BorderSizePixel = 0
timelineRoot.Size = UDim2.fromScale(1, 1)
timelineRoot.Parent = timelineWidget

local function timelineLabel(name: string, text: string, y: number, height: number, size: number): TextLabel
    local label = Instance.new("TextLabel")
    label.Name = name
    label.BackgroundTransparency = 1
    label.Position = UDim2.new(0, 12, 0, y)
    label.Size = UDim2.new(1, -24, 0, height)
    label.Font = Enum.Font.SourceSans
    label.Text = text
    label.TextColor3 = Color3.fromRGB(232, 236, 240)
    label.TextSize = size
    label.TextWrapped = true
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.TextYAlignment = Enum.TextYAlignment.Center
    label.Parent = timelineRoot
    return label
end

local function timelineButton(name: string, text: string, parent: Instance): TextButton
    local buttonInstance = Instance.new("TextButton")
    buttonInstance.Name = name
    buttonInstance.AutoButtonColor = true
    buttonInstance.BackgroundColor3 = Color3.fromRGB(47, 51, 58)
    buttonInstance.BorderSizePixel = 0
    buttonInstance.Font = Enum.Font.SourceSansSemibold
    buttonInstance.Text = text
    buttonInstance.TextColor3 = Color3.fromRGB(230, 234, 239)
    buttonInstance.TextSize = 14
    buttonInstance.Parent = parent
    return buttonInstance
end

local timelineTitle = timelineLabel("Title", "No attack selected", 8, 30, 18)
local timelineHint = timelineLabel("Hint", "Open an attack from Asset Manager / Timelines.", 38, 24, 12)
timelineHint.TextColor3 = Color3.fromRGB(155, 162, 172)

local timelineViewport = Instance.new("ViewportFrame")
timelineViewport.Name = "Preview"
timelineViewport.Active = true
timelineViewport.BackgroundColor3 = Color3.fromRGB(12, 16, 21)
timelineViewport.BorderSizePixel = 0
timelineViewport.Position = UDim2.new(0, 12, 0, 70)
timelineViewport.Size = UDim2.new(1, -24, 0, 250)
timelineViewport.Ambient = Color3.fromRGB(120, 120, 120)
timelineViewport.LightColor = Color3.fromRGB(235, 235, 235)
timelineViewport.LightDirection = Vector3.new(-1, -1, -1)
timelineViewport.Parent = timelineRoot
local timelineViewportCorner = Instance.new("UICorner")
timelineViewportCorner.CornerRadius = UDim.new(0, 6)
timelineViewportCorner.Parent = timelineViewport
local timelineWorld = Instance.new("WorldModel")
timelineWorld.Name = "TimelinePreviewWorld"
timelineWorld.Parent = timelineViewport
local timelineCamera = Instance.new("Camera")
timelineCamera.Name = "TimelinePreviewCamera"
timelineCamera.FieldOfView = 32
timelineCamera.Parent = timelineViewport
timelineViewport.CurrentCamera = timelineCamera
local timelineViewportEmpty = Instance.new("TextLabel")
timelineViewportEmpty.Name = "Empty"
timelineViewportEmpty.BackgroundTransparency = 1
timelineViewportEmpty.Position = UDim2.new(0, 12, 0.5, -14)
timelineViewportEmpty.Size = UDim2.new(1, -24, 0, 28)
timelineViewportEmpty.Font = Enum.Font.SourceSans
timelineViewportEmpty.Text = "Choose an attack — preview appears here"
timelineViewportEmpty.TextColor3 = Color3.fromRGB(118, 132, 146)
timelineViewportEmpty.TextSize = 13
timelineViewportEmpty.TextXAlignment = Enum.TextXAlignment.Center
timelineViewportEmpty.Parent = timelineViewport
local timelineViewportHint = Instance.new("TextLabel")
timelineViewportHint.Name = "Hint"
timelineViewportHint.BackgroundTransparency = 1
timelineViewportHint.Position = UDim2.fromOffset(10, 7)
timelineViewportHint.Size = UDim2.new(1, -20, 0, 18)
timelineViewportHint.Font = Enum.Font.SourceSans
timelineViewportHint.Text = "LMB + drag — orbit  ·  wheel — zoom"
timelineViewportHint.TextColor3 = Color3.fromRGB(126, 140, 153)
timelineViewportHint.TextSize = 11
timelineViewportHint.TextXAlignment = Enum.TextXAlignment.Left
timelineViewportHint.ZIndex = 5
timelineViewportHint.Parent = timelineViewport

local timelineTime = timelineLabel("Time", "0.000 s · 0.0%", 326, 22, 13)

local timelineBar = Instance.new("Frame")
timelineBar.Name = "Scrubber"
timelineBar.Active = true
timelineBar.BackgroundColor3 = Color3.fromRGB(57, 61, 69)
timelineBar.BorderSizePixel = 0
timelineBar.Position = UDim2.new(0, 16, 0, 354)
timelineBar.Size = UDim2.new(1, -32, 0, 18)
timelineBar.Parent = timelineRoot

local timelineFill = Instance.new("Frame")
timelineFill.Name = "Fill"
timelineFill.BackgroundColor3 = Color3.fromRGB(69, 214, 177)
timelineFill.BorderSizePixel = 0
timelineFill.Size = UDim2.new(0, 0, 1, 0)
timelineFill.Parent = timelineBar

local timelineThumb = Instance.new("Frame")
timelineThumb.Name = "Thumb"
timelineThumb.AnchorPoint = Vector2.new(0.5, 0.5)
timelineThumb.BackgroundColor3 = Color3.fromRGB(242, 245, 247)
timelineThumb.BorderSizePixel = 0
timelineThumb.Position = UDim2.new(0, 0, 0.5, 0)
timelineThumb.Size = UDim2.fromOffset(4, 28)
timelineThumb.Parent = timelineBar

local timelineEventHeading = timelineLabel("EventHeading", "Assign selected moment to event", 384, 20, 13)

local timelineEventButtons = Instance.new("Frame")
timelineEventButtons.Name = "EventButtons"
timelineEventButtons.BackgroundTransparency = 1
timelineEventButtons.Position = UDim2.new(0, 12, 0, 410)
timelineEventButtons.Size = UDim2.new(1, -24, 0, 70)
timelineEventButtons.Parent = timelineRoot

local timelineMarkers = timelineLabel("Markers", "No event points", 486, 40, 12)
timelineMarkers.TextColor3 = Color3.fromRGB(170, 178, 188)
timelineMarkers.TextYAlignment = Enum.TextYAlignment.Top

local timelineConfirm = timelineButton("Confirm", "Confirm point", timelineRoot)
timelineConfirm.Position = UDim2.new(0, 12, 0, 534)
timelineConfirm.Size = UDim2.new(1, -24, 0, 36)

local timelineStatus = timelineLabel("Status", "Studio editor idle", 578, 42, 12)
timelineStatus.TextColor3 = Color3.fromRGB(155, 162, 172)
timelineStatus.TextYAlignment = Enum.TextYAlignment.Top

local function timelineEventDefinition(eventName: string): any?
    for _, definition in ipairs(timelineEditor.eventCatalog) do
        if tostring(definition.name or "") == eventName then
            return definition
        end
    end
    return nil
end

local function timelineRefreshMarkers()
    local rows = {}
    for _, definition in ipairs(timelineEditor.eventCatalog) do
        local eventName = tostring(definition.name or "")
        local event = timelineEditor.events[eventName]
        if type(event) == "table" then
            table.insert(rows, ("%s %.1f%%"):format(eventName, (tonumber(event.normalizedTime) or 0) * 100))
        end
    end
    timelineMarkers.Text = if #rows > 0 then table.concat(rows, "  ·  ") else "No event points"
end

local function addTimelineTarget(targetMap: any, name: string, target: Instance)
    if name == "" then
        return
    end
    local bucket = targetMap[name]
    if bucket == nil then
        bucket = {}
        targetMap[name] = bucket
    end
    if table.find(bucket, target) == nil then
        table.insert(bucket, target)
    end
end

local function collectTimelineTargets(preview: Model): any
    local targetMap = {}
    for _, descendant in ipairs(preview:GetDescendants()) do
        if descendant:IsA("Bone") then
            addTimelineTarget(targetMap, descendant.Name, descendant)
        elseif descendant:IsA("Motor6D") then
            addTimelineTarget(targetMap, descendant.Name, descendant)
            if descendant.Part1 ~= nil then
                addTimelineTarget(targetMap, descendant.Part1.Name, descendant)
            end
        end
    end
    return targetMap
end

local function timelineTargetTransform(target: Instance): CFrame
    if target:IsA("Bone") or target:IsA("Motor6D") then
        return target.Transform
    end
    return CFrame.new()
end

local function setTimelineTargetTransform(target: Instance, transform: CFrame)
    if target:IsA("Bone") or target:IsA("Motor6D") then
        target.Transform = transform
    end
end

local function timelinePoseTarget(pose: Pose, targetMap: any): Instance?
    local bucket = targetMap[pose.Name]
    if bucket == nil or #bucket == 0 then
        return nil
    end
    if #bucket == 1 then
        return bucket[1]
    end
    local parentPose = pose.Parent
    if parentPose and parentPose:IsA("Pose") then
        for _, candidate in ipairs(bucket) do
            if candidate:IsA("Bone") then
                local candidateParent = candidate.Parent
                if candidateParent and candidateParent.Name == parentPose.Name then
                    return candidate
                end
            elseif candidate:IsA("Motor6D") and candidate.Part0 and candidate.Part0.Name == parentPose.Name then
                return candidate
            end
        end
    end
    return bucket[1]
end

local function buildTimelinePoseTracks(preview: Model, sequence: KeyframeSequence): any
    local targetMap = collectTimelineTargets(preview)
    local tracksByTarget = {}
    local keyframes = sequence:GetKeyframes()
    table.sort(keyframes, function(a, b)
        return a.Time < b.Time
    end)
    for _, keyframe in ipairs(keyframes) do
        for _, descendant in ipairs(keyframe:GetDescendants()) do
            if descendant:IsA("Pose") then
                local target = timelinePoseTarget(descendant, targetMap)
                if target ~= nil then
                    local track = tracksByTarget[target]
                    if track == nil then
                        track = {
                            target = target,
                            defaultTransform = timelineTargetTransform(target),
                            samples = {},
                        }
                        tracksByTarget[target] = track
                    end
                    table.insert(track.samples, {
                        time = keyframe.Time,
                        cframe = descendant.CFrame,
                        style = descendant.EasingStyle.Name,
                        direction = descendant.EasingDirection.Name,
                    })
                end
            end
        end
    end
    local tracks = {}
    for _, track in pairs(tracksByTarget) do
        table.sort(track.samples, function(a, b)
            return a.time < b.time
        end)
        table.insert(tracks, track)
    end
    return tracks
end

local easingStyles = {}
for _, item in ipairs(Enum.EasingStyle:GetEnumItems()) do
    easingStyles[item.Name] = item
end
local easingDirections = {}
for _, item in ipairs(Enum.EasingDirection:GetEnumItems()) do
    easingDirections[item.Name] = item
end

local function timelineEasingAlpha(alpha: number, styleName: string, directionName: string): number
    alpha = math.clamp(alpha, 0, 1)
    if styleName == "Constant" then
        return if alpha >= 1 then 1 else 0
    end
    local style = easingStyles[styleName] or Enum.EasingStyle.Linear
    local direction = easingDirections[directionName] or Enum.EasingDirection.Out
    local ok, value = pcall(function()
        return TweenService:GetValue(alpha, style, direction)
    end)
    return if ok then value else alpha
end

local function sampleTimelineTrack(track: any, timePosition: number): CFrame
    local samples = track.samples
    if #samples == 0 then
        return track.defaultTransform
    end
    if timePosition <= samples[1].time then
        if samples[1].time <= 0.0005 then
            return samples[1].cframe
        end
        local alpha = timelineEasingAlpha(timePosition / samples[1].time, "Linear", "Out")
        return track.defaultTransform:Lerp(samples[1].cframe, alpha)
    end
    for index = 1, #samples - 1 do
        local current = samples[index]
        local following = samples[index + 1]
        if timePosition <= following.time then
            local span = math.max(following.time - current.time, 0.000001)
            local alpha = timelineEasingAlpha((timePosition - current.time) / span, current.style, current.direction)
            return current.cframe:Lerp(following.cframe, alpha)
        end
    end
    return samples[#samples].cframe
end

local function applyTimelinePose(timePosition: number)
    for _, track in ipairs(timelineEditor.poseTracks) do
        if track.target.Parent ~= nil then
            setTimelineTargetTransform(track.target, sampleTimelineTrack(track, timePosition))
        end
    end
end

local function timelineSetNormalized(value: number)
    local normalized = math.clamp(tonumber(value) or 0, 0, 1)
    timelineEditor.normalized = normalized
    timelineFill.Size = UDim2.new(normalized, 0, 1, 0)
    timelineThumb.Position = UDim2.new(normalized, 0, 0.5, 0)
    local duration = math.max(0, tonumber(timelineEditor.duration) or 0)
    timelineTime.Text = ("%.3f s · %.1f%%"):format(duration * normalized, normalized * 100)
    if duration > 0 and #timelineEditor.poseTracks > 0 then
        local ok, err = pcall(function()
            applyTimelinePose(duration * normalized)
        end)
        if not ok then
            timelineStatus.Text = "Pose preview failed: " .. tostring(err)
        end
    end
end

local function timelineSelectEvent(eventName: string)
    if timelineEventDefinition(eventName) == nil then
        return
    end
    timelineEditor.selectedEvent = eventName
    for _, child in ipairs(timelineEventButtons:GetChildren()) do
        if child:IsA("TextButton") then
            child.BackgroundColor3 = if child.Name == eventName then Color3.fromRGB(49, 112, 96) else Color3.fromRGB(47, 51, 58)
        end
    end
    local existing = timelineEditor.events[eventName]
    if type(existing) == "table" and tonumber(existing.normalizedTime) ~= nil then
        timelineSetNormalized(tonumber(existing.normalizedTime) or 0)
    end
end

local function timelineBuildEventButtons()
    for _, child in ipairs(timelineEventButtons:GetChildren()) do
        child:Destroy()
    end
    local count = math.max(1, #timelineEditor.eventCatalog)
    local gap = 6
    local widthScale = 1 / math.min(count, 3)
    for index, definition in ipairs(timelineEditor.eventCatalog) do
        local eventName = tostring(definition.name or "")
        if eventName ~= "" then
            local buttonInstance = timelineButton(eventName, tostring(definition.label or eventName), timelineEventButtons)
            local column = (index - 1) % 3
            local row = math.floor((index - 1) / 3)
            buttonInstance.Position = UDim2.new(column * widthScale, column == 0 and 0 or gap, 0, row * 36)
            buttonInstance.Size = UDim2.new(widthScale, -gap, 0, 30)
            buttonInstance.MouseButton1Click:Connect(function()
                timelineSelectEvent(eventName)
            end)
        end
    end
    if timelineEventDefinition(timelineEditor.selectedEvent) == nil and #timelineEditor.eventCatalog > 0 then
        timelineEditor.selectedEvent = tostring(timelineEditor.eventCatalog[1].name or "")
    end
    timelineSelectEvent(timelineEditor.selectedEvent)
end

local function timelineNormalizedFromInput(input: InputObject): number
    local width = math.max(1, timelineBar.AbsoluteSize.X)
    return math.clamp((input.Position.X - timelineBar.AbsolutePosition.X) / width, 0, 1)
end

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

timelineBar.InputBegan:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1 then
        timelineDragging = true
        timelineSetNormalized(timelineNormalizedFromInput(input))
    end
end)

timelineViewport.InputBegan:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1 and timelineEditor.preview ~= nil then
        timelinePreviewDragging = true
    end
end)

timelineViewport.InputChanged:Connect(function(input)
    if timelineEditor.preview == nil then
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

UserInputService.InputChanged:Connect(function(input)
    if timelineDragging and input.UserInputType == Enum.UserInputType.MouseMovement then
        timelineSetNormalized(timelineNormalizedFromInput(input))
    end
end)
UserInputService.InputEnded:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1 then
        timelineDragging = false
        timelinePreviewDragging = false
    end
end)

local function postTimelineAgent(payload: any): any
    local response = HttpService:RequestAsync({
        Url = AGENT_BASE_URL .. "/api/timelines/editor-event",
        Method = "POST",
        Headers = {
            ["X-Control-Token"] = AGENT_TOKEN,
            ["Content-Type"] = "application/json",
        },
        Body = HttpService:JSONEncode(payload),
    })
    if not response.Success then
        error(("Asset Manager rejected timeline update (HTTP %d): %s"):format(response.StatusCode, response.Body))
    end
    local ok, decoded = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if ok then
        return decoded
    end
    return nil
end

local function postTimelineEditorResult(payload: any)
    local response = HttpService:RequestAsync({
        Url = BRIDGE_URL .. "/timeline-editor-result",
        Method = "POST",
        Headers = {
            ["X-Game1-Token"] = BRIDGE_TOKEN,
            ["Content-Type"] = "application/json",
        },
        Body = HttpService:JSONEncode(payload),
    })
    if not response.Success then
        error("game1 timeline editor bridge rejected response: " .. tostring(response.StatusCode))
    end
end

local function destroyTimelinePreview()
    timelineEditor.poseTracks = {}
    if timelineEditor.preview ~= nil then
        pcall(function()
            timelineEditor.preview:Destroy()
        end)
        timelineEditor.preview = nil
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

local function handleTimelineEditor(data: any)
    local result = {
        command = "timeline-editor",
        project = "game1",
        schemaVersion = 1,
        sessionId = tostring(data.sessionId or ""),
        clipId = tostring(data.clipId or ""),
    }
    local ok, operationError = xpcall(function()
        if tostring(data.project or "") ~= "game1" or tonumber(data.schemaVersion) ~= 1 then
            error("invalid game1 timeline editor command")
        end
        local sessionId = tostring(data.sessionId or "")
        local modelAssetId = tonumber(data.modelAssetId)
        local animationAssetId = tonumber(data.animationAssetId)
        if sessionId == "" or modelAssetId == nil or modelAssetId <= 0 or animationAssetId == nil or animationAssetId <= 0 then
            error("timeline editor command is missing published asset ids")
        end
        destroyTimelinePreview()

        timelineEditor.sessionId = sessionId
        timelineEditor.clipId = tostring(data.clipId or "")
        timelineEditor.clipName = tostring(data.clipName or timelineEditor.clipId)
        timelineEditor.subjectName = tostring(data.subjectName or data.subjectId or "")
        timelineEditor.duration = math.max(0, tonumber(data.duration) or 0)
        timelineEditor.normalized = 0
        timelineEditor.eventCatalog = if type(data.eventCatalog) == "table" then data.eventCatalog else {}
        timelineEditor.events = if type(data.events) == "table" then data.events else {}
        timelineEditor.selectedEvent = "Hit"

        local preview = loadTimelinePreviewModel(modelAssetId)
        timelineEditor.preview = preview
        local sequence = loadTimelineSequence(animationAssetId)
        local sequenceDuration = timelineSequenceDuration(sequence)
        if sequenceDuration <= 0 then
            sequence:Destroy()
            error("selected attack animation contains no timed keyframes")
        end
        timelineEditor.duration = sequenceDuration
        timelineEditor.poseTracks = buildTimelinePoseTracks(preview, sequence)
        sequence:Destroy()
        if #timelineEditor.poseTracks == 0 then
            error("selected attack has no Pose targets matching the preview rig")
        end

        timelineTitle.Text = timelineEditor.subjectName .. " · " .. timelineEditor.clipName
        timelineHint.Text = "Preview is rendered inside this plugin. Scrub, choose an event, then Confirm point."
        timelineStatus.Text = ("Ready · %.3f s · %d animated target(s)"):format(
            timelineEditor.duration,
            #timelineEditor.poseTracks
        )
        timelineBuildEventButtons()
        timelineRefreshMarkers()
        timelineSetNormalized(0)
        timelineWidget.Enabled = true

        postTimelineAgent({
            sessionId = timelineEditor.sessionId,
            action = "ready",
            duration = timelineEditor.duration,
        })
        result.duration = timelineEditor.duration
        result.preview = "ViewportFrame/TimelinePreviewWorld/" .. TIMELINE_PREVIEW_NAME
        result.animatedTargets = #timelineEditor.poseTracks
    end, debug.traceback)

    if not ok then
        result.error = tostring(operationError)
        timelineStatus.Text = "Timeline editor error: " .. tostring(operationError)
        warn("[game1 plugin] timeline editor failed: " .. tostring(operationError))
    end
    local postOk, postError = pcall(postTimelineEditorResult, result)
    if not postOk then
        warn("[game1 plugin] failed to report timeline editor result: " .. tostring(postError))
    end
end

timelineConfirm.MouseButton1Click:Connect(function()
    if timelineEditor.sessionId == "" or timelineEditor.selectedEvent == "" then
        return
    end
    local eventName = timelineEditor.selectedEvent
    local normalized = timelineEditor.normalized
    local definition = timelineEventDefinition(eventName)
    local event = { normalizedTime = normalized }
    if definition and tostring(definition.result or "") ~= "" then
        event.result = tostring(definition.result)
    end
    timelineEditor.events[eventName] = event
    timelineRefreshMarkers()
    timelineStatus.Text = ("Sending %s = %.1f%% to Asset Manager…"):format(eventName, normalized * 100)
    local ok, err = pcall(function()
        postTimelineAgent({
            sessionId = timelineEditor.sessionId,
            action = "set-event",
            eventName = eventName,
            normalizedTime = normalized,
            duration = timelineEditor.duration,
        })
    end)
    if ok then
        timelineStatus.Text = ("Confirmed %s = %.3f s (%.1f%%)"):format(
            eventName,
            timelineEditor.duration * normalized,
            normalized * 100
        )
    else
        timelineStatus.Text = "Confirm failed: " .. tostring(err)
        warn("[game1 plugin] timeline confirm failed: " .. tostring(err))
    end
end)

local function pollBridge()
    if RunService:IsRunning() then
        return
    end
    local ok, response = pcall(HttpService.RequestAsync, HttpService, {
        Url = BRIDGE_URL .. "/command",
        Method = "GET",
        Headers = { ["X-Game1-Token"] = BRIDGE_TOKEN },
    })
    if not ok or not response.Success then
        return
    end
    local decodeOk, data = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if not decodeOk or type(data) ~= "table" then
        return
    end
    if data.command == "model-load" then
        handleModelLoad(data)
    elseif data.command == "monster-spawn" then
        handleMonsterSpawn(data)
    elseif data.command == "timeline-editor" then
        handleTimelineEditor(data)
    elseif data.command == "location-authoring" then
        locationCommands.handle(data)
    end
end

task.spawn(function()
    while true do
        pollBridge()
        task.wait(1)
    end
end)

print("[game1 plugin] loaded · model bridge v24 · DecoManager identity-only placement + environment bounce authoring + locations + viewport timeline pose sampler")

-- Timeline editor view. Builds the dock widget and exposes only its controls.
local StudioTimelineWidget = {}

function StudioTimelineWidget.new(plugin)
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

    return {
        widget = timelineWidget,
        title = timelineTitle,
        hint = timelineHint,
        viewport = timelineViewport,
        world = timelineWorld,
        camera = timelineCamera,
        empty = timelineViewportEmpty,
        time = timelineTime,
        bar = timelineBar,
        fill = timelineFill,
        thumb = timelineThumb,
        eventButtons = timelineEventButtons,
        markers = timelineMarkers,
        confirm = timelineConfirm,
        status = timelineStatus,
        makeButton = timelineButton,
    }
end

return table.freeze(StudioTimelineWidget)

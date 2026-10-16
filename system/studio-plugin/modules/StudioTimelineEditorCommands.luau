-- Timeline authoring session: validates requests, binds UI events and reports results.
-- No gameplay state is mutated; all previews live inside the plugin WorldModel.
local StudioTimelineWidget = require(script.Parent.StudioTimelineWidget)
local StudioTimelinePreview = require(script.Parent.StudioTimelinePreview)
local StudioTimelinePoseSampler = require(script.Parent.StudioTimelinePoseSampler)
local StudioTimelineTransport = require(script.Parent.StudioTimelineTransport)

return function(services)
    local UserInputService = services.UserInputService
    local view = StudioTimelineWidget.new(services.plugin)
    local timelineWidget = view.widget
    local timelineTitle = view.title
    local timelineHint = view.hint
    local timelineTime = view.time
    local timelineBar = view.bar
    local timelineFill = view.fill
    local timelineThumb = view.thumb
    local timelineEventButtons = view.eventButtons
    local timelineMarkers = view.markers
    local timelineConfirm = view.confirm
    local timelineStatus = view.status
    local timelineButton = view.makeButton
    local poseSampler = StudioTimelinePoseSampler.new(services.TweenService)
    local previewService = StudioTimelinePreview.new({
        AssetService = services.AssetService,
        AnimationClipProvider = services.AnimationClipProvider,
        UserInputService = UserInputService,
        viewport = view.viewport,
        world = view.world,
        camera = view.camera,
        empty = view.empty,
    })
    local transport = StudioTimelineTransport.new({
        HttpService = services.HttpService,
        agentBaseUrl = services.agentBaseUrl,
        agentToken = services.agentToken,
        bridgeUrl = services.bridgeUrl,
        bridgeToken = services.bridgeToken,
    })
    local postTimelineAgent = transport.PostAgent
    local postTimelineEditorResult = transport.PostResult
    local loadTimelinePreviewModel = previewService.LoadModel
    local loadTimelineSequence = previewService.LoadSequence
    local timelineSequenceDuration = previewService.SequenceDuration
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
    local destroyTimelinePreview = function()
        timelineEditor.poseTracks = {}
        timelineEditor.preview = nil
        previewService.DestroyPreview()
    end
    local timelineDragging = false
    local TIMELINE_PREVIEW_NAME = "Game1TimelinePreview"

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

    local function timelineSetNormalized(value: number)
        local normalized = math.clamp(tonumber(value) or 0, 0, 1)
        timelineEditor.normalized = normalized
        timelineFill.Size = UDim2.new(normalized, 0, 1, 0)
        timelineThumb.Position = UDim2.new(normalized, 0, 0.5, 0)
        local duration = math.max(0, tonumber(timelineEditor.duration) or 0)
        timelineTime.Text = ("%.3f s · %.1f%%"):format(duration * normalized, normalized * 100)
        if duration > 0 and #timelineEditor.poseTracks > 0 then
            local ok, err = pcall(function()
                poseSampler.Apply(timelineEditor.poseTracks, duration * normalized)
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

    timelineBar.InputBegan:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 then
            timelineDragging = true
            timelineSetNormalized(timelineNormalizedFromInput(input))
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
        end
    end)

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
            timelineEditor.poseTracks = poseSampler.Build(preview, sequence)
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


    return handleTimelineEditor
end

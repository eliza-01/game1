-- Polygon Location authoring commands for game1 Asset Manager.
return function(Context)
    local HttpService = Context.HttpService
    local Selection = Context.Selection
    local Workspace = Context.Workspace
    local UserInputService = Context.UserInputService
    local BRIDGE_URL = Context.BRIDGE_URL
    local BRIDGE_TOKEN = Context.BRIDGE_TOKEN
    local plugin = Context.plugin

    local AUTHORING_ROOT = "Game1Authoring"
    local LOCATION_FOLDER = "Locations"

    local function postResult(payload: any)
        local response = HttpService:RequestAsync({
            Url = BRIDGE_URL .. "/location-authoring-result",
            Method = "POST",
            Headers = {
                ["X-Game1-Token"] = BRIDGE_TOKEN,
                ["Content-Type"] = "application/json",
            },
            Body = HttpService:JSONEncode(payload),
        })
        if not response.Success then
            error("game1 Location authoring result bridge rejected response: " .. tostring(response.StatusCode))
        end
    end

    local function locationFolder(): Folder
        local root = Workspace:FindFirstChild(AUTHORING_ROOT)
        if root and not root:IsA("Folder") then
            error("Workspace." .. AUTHORING_ROOT .. " exists but is not a Folder")
        end
        if not root then
            root = Instance.new("Folder")
            root.Name = AUTHORING_ROOT
            root:SetAttribute("Game1Authoring", true)
            root.Parent = Workspace
        end
        local folder = root:FindFirstChild(LOCATION_FOLDER)
        if folder and not folder:IsA("Folder") then
            error(root:GetFullName() .. "." .. LOCATION_FOLDER .. " exists but is not a Folder")
        end
        if not folder then
            folder = Instance.new("Folder")
            folder.Name = LOCATION_FOLDER
            folder.Parent = root
        end
        return folder :: Folder
    end

    local function findLocationMarker(locationId: string): Model?
        local root = Workspace:FindFirstChild(AUTHORING_ROOT)
        local folder = root and root:FindFirstChild(LOCATION_FOLDER)
        if not folder then
            return nil
        end
        for _, child in ipairs(folder:GetChildren()) do
            if child:IsA("Model") and tostring(child:GetAttribute("LocationId") or "") == locationId then
                return child
            end
        end
        return nil
    end

    local function safeName(value: any): string
        local name = tostring(value or "Location"):gsub("[^%w]+", "_"):gsub("^_+", ""):gsub("_+$", "")
        return name ~= "" and name or "Location"
    end

    local function markerName(data: any): string
        local shortId = tostring(data.locationId or "location"):gsub("^location%-", ""):sub(1, 8)
        return string.format("%s_%s", safeName(data.name), shortId)
    end

    local function pointFromData(value: any): Vector3
        if typeof(value) ~= "table" then
            error("Location point is invalid")
        end
        local x = tonumber(value.x)
        local y = tonumber(value.y)
        local z = tonumber(value.z)
        if not x or not y or not z then
            error("Location point coordinates are invalid")
        end
        return Vector3.new(x, y, z)
    end

    local function markerPart(
        parent: Instance,
        name: string,
        size: Vector3,
        cframe: CFrame,
        color: Color3,
        transparency: number
    ): Part
        local item = Instance.new("Part")
        item.Name = name
        item.Anchored = true
        item.CanCollide = false
        item.CanTouch = false
        item.CanQuery = false
        item.CastShadow = false
        item.Material = Enum.Material.Neon
        item.Color = color
        item.Transparency = transparency
        item.Size = size
        item.CFrame = cframe
        item.Parent = parent
        return item
    end

    local function linePart(
        parent: Instance,
        name: string,
        a: Vector3,
        b: Vector3,
        color: Color3,
        transparency: number
    ): Part?
        local delta = b - a
        local length = delta.Magnitude
        if length < 0.02 then
            return nil
        end
        return markerPart(
            parent,
            name,
            Vector3.new(0.16, 0.16, length),
            CFrame.lookAt((a + b) * 0.5, b),
            color,
            transparency
        )
    end

    local function addLabel(marker: Model, adornee: BasePart, data: any, preview: boolean)
        local billboard = Instance.new("BillboardGui")
        billboard.Name = "Label"
        billboard.Adornee = adornee
        billboard.AlwaysOnTop = true
        billboard.LightInfluence = 0
        billboard.Size = UDim2.fromOffset(260, 52)
        billboard.StudsOffsetWorldSpace = Vector3.new(0, 2.4, 0)
        billboard.Parent = marker

        local text = Instance.new("TextLabel")
        text.BackgroundColor3 = Color3.fromRGB(17, 22, 30)
        text.BackgroundTransparency = 0.1
        text.BorderSizePixel = 0
        text.Size = UDim2.fromScale(1, 1)
        text.Font = Enum.Font.GothamSemibold
        text.TextColor3 = Color3.fromRGB(246, 248, 251)
        text.TextSize = 14
        text.TextWrapped = true
        text.Text = string.format("%s\nLocation%s", tostring(data.name or "Location"), preview and " · DRAW" or "")
        text.Parent = billboard

        local corner = Instance.new("UICorner")
        corner.CornerRadius = UDim.new(0, 7)
        corner.Parent = text
    end

    local function clearCopies(locationId: string, preview: boolean)
        for _, child in ipairs(locationFolder():GetChildren()) do
            if child:IsA("Model") then
                local registered = not preview and tostring(child:GetAttribute("LocationId") or "") == locationId
                local previewCopy = tostring(child:GetAttribute("PreviewForLocationId") or "") == locationId
                if registered or previewCopy then
                    child:Destroy()
                end
            end
        end
    end

    local function createLocationMarker(data: any, preview: boolean): Model
        local locationId = tostring(data.locationId or "")
        if not locationId:match("^location%-%w[%w%-]+$") then
            error("Location command has invalid locationId")
        end
        local values = typeof(data.points) == "table" and data.points or {}
        if #values < 3 then
            error("Registered Location polygon must contain at least 3 points")
        end
        clearCopies(locationId, preview)

        local marker = Instance.new("Model")
        marker.Name = markerName(data)
        marker:SetAttribute("Game1LocationMarker", true)
        marker:SetAttribute("LocationId", preview and "" or locationId)
        if preview then
            marker:SetAttribute("PreviewForLocationId", locationId)
        end
        marker:SetAttribute("LocationName", tostring(data.name or "Location"))
        marker:SetAttribute("PlaceId", tonumber(data.placeId) or game.PlaceId)
        marker.Parent = locationFolder()

        local color = preview and Color3.fromRGB(255, 161, 84) or Color3.fromRGB(66, 214, 177)
        local points = {}
        for index, raw in ipairs(values) do
            local world = pointFromData(raw)
            table.insert(points, world)
            local vertex = markerPart(
                marker,
                string.format("Point_%03d", index),
                Vector3.new(0.75, 0.75, 0.75),
                CFrame.new(world),
                color,
                0.08
            )
            vertex.Shape = Enum.PartType.Ball
            vertex:SetAttribute("LocationVertexIndex", index)
        end
        for index = 1, #points do
            local nextIndex = index == #points and 1 or index + 1
            linePart(marker, string.format("Edge_%03d", index), points[index], points[nextIndex], color, 0.08)
        end
        local first = marker:FindFirstChild("Point_001")
        if first and first:IsA("BasePart") then
            marker.PrimaryPart = first
            addLabel(marker, first, data, preview)
        end
        Selection:Set({ marker })
        return marker
    end

    local function createDrawPreview(data: any): (Model, Part)
        local locationId = tostring(data.locationId or "")
        clearCopies(locationId, true)
        local marker = Instance.new("Model")
        marker.Name = "DRAW_" .. markerName(data)
        marker:SetAttribute("Game1LocationMarker", true)
        marker:SetAttribute("PreviewForLocationId", locationId)
        marker:SetAttribute("LocationName", tostring(data.name or "Location"))
        marker.Parent = locationFolder()
        local liveEdge = markerPart(
            marker,
            "LiveEdge",
            Vector3.new(0.1, 0.1, 0.1),
            CFrame.new(),
            Color3.fromRGB(255, 161, 84),
            0.2
        )
        return marker, liveEdge
    end

    local function updateLiveEdge(liveEdge: Part, a: Vector3?, b: Vector3?)
        if not a or not b or (b - a).Magnitude < 0.02 then
            liveEdge.Transparency = 1
            return
        end
        local length = (b - a).Magnitude
        liveEdge.Size = Vector3.new(0.12, 0.12, length)
        liveEdge.CFrame = CFrame.lookAt((a + b) * 0.5, b)
        liveEdge.Transparency = 0.22
    end

    local function drawResult(data: any): any
        local mouse = plugin:GetMouse()
        local marker, liveEdge = createDrawPreview(data)
        local color = Color3.fromRGB(255, 161, 84)
        local points: { Vector3 } = {}
        local finished = false
        local cancelled = false
        local firstVertex: Part? = nil

        plugin:Activate(true)
        local moveConnection = mouse.Move:Connect(function()
            if #points > 0 and mouse.Target then
                updateLiveEdge(liveEdge, points[#points], mouse.Hit.Position)
            end
        end)
        local clickConnection = mouse.Button1Down:Connect(function()
            if not mouse.Target then
                return
            end
            if firstVertex and mouse.Target == firstVertex then
                if #points >= 3 then
                    finished = true
                end
                return
            end
            if mouse.Target:IsDescendantOf(marker) then
                return
            end
            local world = mouse.Hit.Position
            table.insert(points, world)
            local index = #points
            local vertex = markerPart(
                marker,
                string.format("Point_%03d", index),
                Vector3.new(1.05, 1.05, 1.05),
                CFrame.new(world),
                color,
                0.04
            )
            vertex.Shape = Enum.PartType.Ball
            vertex:SetAttribute("LocationVertexIndex", index)
            if index == 1 then
                firstVertex = vertex
                vertex.CanQuery = true
                addLabel(marker, vertex, data, true)
            elseif index > 1 then
                linePart(marker, string.format("Edge_%03d", index - 1), points[index - 1], world, color, 0.08)
            end
        end)
        local inputConnection = UserInputService.InputBegan:Connect(function(input, processed)
            if not processed and input.KeyCode == Enum.KeyCode.Escape then
                cancelled = true
            end
        end)

        local deadline = os.clock() + 295
        repeat
            task.wait(0.05)
        until finished or cancelled or os.clock() >= deadline
        moveConnection:Disconnect()
        clickConnection:Disconnect()
        inputConnection:Disconnect()
        plugin:Deactivate()

        if not finished then
            marker:Destroy()
            error(cancelled and "Location drawing was cancelled" or "Location drawing timed out")
        end
        liveEdge:Destroy()
        if firstVertex then
            firstVertex.CanQuery = false
        end
        linePart(marker, string.format("Edge_%03d", #points), points[#points], points[1], color, 0.08)

        local resultPoints = {}
        for _, world in ipairs(points) do
            table.insert(resultPoints, { x = world.X, y = world.Y, z = world.Z })
        end
        Selection:Set({ marker })
        return {
            points = resultPoints,
            placeId = game.PlaceId,
            markerPath = marker:GetFullName(),
            closed = true,
        }
    end

    local function validatePlace(data: any)
        local expectedPlaceId = tonumber(data.placeId) or 0
        if expectedPlaceId > 0 and game.PlaceId > 0 and expectedPlaceId ~= game.PlaceId then
            error(string.format("Open PlaceId %d does not match Location PlaceId %d", game.PlaceId, expectedPlaceId))
        end
    end

    local function handle(data: any)
        local payload = {
            schemaVersion = 1,
            project = "game1",
            command = "location-authoring",
            action = tostring(data.action or ""),
            operationId = tostring(data.operationId or ""),
            locationId = tostring(data.locationId or ""),
            placeId = game.PlaceId,
            placeName = game.Name,
        }

        local ok, resultOrError = xpcall(function()
            if tostring(data.project or "") ~= "game1" or tonumber(data.schemaVersion) ~= 1 then
                error("invalid game1 Location command")
            end
            validatePlace(data)
            local action = tostring(data.action or "")
            if action == "draw" then
                return drawResult(data)
            elseif action == "upsert" then
                local marker = createLocationMarker(data, false)
                return { markerPath = marker:GetFullName(), synchronized = true }
            elseif action == "select" then
                local marker = findLocationMarker(tostring(data.locationId or ""))
                if not marker then
                    error("Registered Location marker was not found in Studio")
                end
                Selection:Set({ marker })
                local root = marker.PrimaryPart
                local camera = Workspace.CurrentCamera
                if root and camera then
                    camera.CFrame = CFrame.lookAt(root.Position + Vector3.new(18, 16, 18), root.Position)
                end
                return { markerPath = marker:GetFullName(), synchronized = true }
            elseif action == "delete" then
                local marker = findLocationMarker(tostring(data.locationId or ""))
                if marker then
                    marker:Destroy()
                end
                for _, child in ipairs(locationFolder():GetChildren()) do
                    if child:IsA("Model")
                        and tostring(child:GetAttribute("PreviewForLocationId") or "") == tostring(data.locationId or "") then
                        child:Destroy()
                    end
                end
                return { deleted = marker ~= nil, synchronized = true }
            elseif action == "sync" then
                local folder = locationFolder()
                for _, child in ipairs(folder:GetChildren()) do
                    if child:IsA("Model") and child:GetAttribute("Game1LocationMarker") == true then
                        child:Destroy()
                    end
                end
                local created = 0
                local skipped = 0
                local syncedLocationIds = {}
                for _, record in ipairs(typeof(data.records) == "table" and data.records or {}) do
                    local recordPlaceId = tonumber(record.placeId) or 0
                    if recordPlaceId == 0 or game.PlaceId == 0 or recordPlaceId == game.PlaceId then
                        createLocationMarker(record, false)
                        created += 1
                        table.insert(syncedLocationIds, tostring(record.locationId or ""))
                    else
                        skipped += 1
                    end
                end
                return {
                    synchronized = true,
                    created = created,
                    skipped = skipped,
                    syncedLocationIds = syncedLocationIds,
                }
            end
            error("Unsupported Location action: " .. action)
        end, debug.traceback)

        if ok then
            for key, value in pairs(resultOrError) do
                payload[key] = value
            end
        else
            payload.error = tostring(resultOrError)
        end

        local postOk, postError = pcall(postResult, payload)
        if not postOk then
            warn("[game1 plugin] failed to report Location result: " .. tostring(postError))
        end
    end

    return {
        handle = handle,
    }
end

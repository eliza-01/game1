-- Monster/NPC authored spawn commands and lightweight Studio marker placement.
-- Both kinds intentionally share marker lifecycle; NPC preview gesture remains in NpcSpawnPlacement.
local NpcSpawnPreview = require(script.Parent.NpcSpawnPreview)
local NpcSpawnPlacement = require(script.Parent.NpcSpawnPlacement)

return function(services)
    local plugin = services.plugin
    local HttpService = services.HttpService
    local Selection = services.Selection
    local ServerStorage = services.ServerStorage
    local UserInputService = services.UserInputService
    local Workspace = services.Workspace
    local BRIDGE_URL = services.bridgeUrl
    local BRIDGE_TOKEN = services.bridgeToken

    local MONSTER_SPAWN_AUTHORING_ROOT = "Game1Authoring"
    local MONSTER_SPAWN_MARKER_FOLDER = "MonsterSpawns"

    local function postMonsterSpawnResult(payload: any)
        local response = HttpService:RequestAsync({
            Url = BRIDGE_URL .. "/monster-spawn-result",
            Method = "POST",
            Headers = {
                ["X-Game1-Token"] = BRIDGE_TOKEN,
                ["Content-Type"] = "application/json",
            },
            Body = HttpService:JSONEncode(payload),
        })
        if not response.Success then
            error("game1 Monster Spawn result bridge rejected response: " .. tostring(response.StatusCode))
        end
    end

    local function monsterSpawnMarkerFolder(kind: string?): Folder
        local root = Workspace:FindFirstChild(MONSTER_SPAWN_AUTHORING_ROOT)
        if root and not root:IsA("Folder") then
            error("Workspace." .. MONSTER_SPAWN_AUTHORING_ROOT .. " exists but is not a Folder")
        end
        if not root then
            root = Instance.new("Folder")
            root.Name = MONSTER_SPAWN_AUTHORING_ROOT
            root:SetAttribute("Game1Authoring", true)
            root.Parent = Workspace
        end
        local markerFolderName = if kind == "npc" then "NpcSpawns" else MONSTER_SPAWN_MARKER_FOLDER
        local folder = root:FindFirstChild(markerFolderName)
        if folder and not folder:IsA("Folder") then
            error(root:GetFullName() .. "." .. markerFolderName .. " exists but is not a Folder")
        end
        if not folder then
            folder = Instance.new("Folder")
            folder.Name = markerFolderName
            folder.Parent = root
        end
        return folder :: Folder
    end

    local function findMonsterSpawnMarker(spawnId: string, kind: string?): Model?
        local root = Workspace:FindFirstChild(MONSTER_SPAWN_AUTHORING_ROOT)
        local folder = root and root:FindFirstChild(if kind == "npc" then "NpcSpawns" else MONSTER_SPAWN_MARKER_FOLDER)
        if not folder then
            return nil
        end
        for _, child in ipairs(folder:GetChildren()) do
            if child:IsA("Model") and tostring(child:GetAttribute("SpawnId") or "") == spawnId then
                return child
            end
        end
        return nil
    end

    local function safeMonsterSpawnMarkerPart(parent: Instance, name: string, size: Vector3, cframe: CFrame, color: Color3, transparency: number): Part
        local part = Instance.new("Part")
        part.Name = name
        part.Anchored = true
        part.CanCollide = false
        part.CanQuery = false
        part.CanTouch = false
        part.CastShadow = false
        part.Material = Enum.Material.Neon
        part.Color = color
        part.Size = size
        part.CFrame = cframe
        part.Transparency = transparency
        part.Parent = parent
        return part
    end

    local function monsterSpawnMarkerCFrame(position: any, yawDegrees: any): CFrame
        if typeof(position) ~= "table" then
            error("Monster Spawn position is missing")
        end
        local x = tonumber(position.x)
        local y = tonumber(position.y)
        local z = tonumber(position.z)
        if x == nil or y == nil or z == nil then
            error("Monster Spawn position is invalid")
        end
        return CFrame.new(x, y, z) * CFrame.Angles(0, math.rad(tonumber(yawDegrees) or 0), 0)
    end

    local function monsterSpawnMarkerName(data: any): string
        local name = tostring(data.monsterName or data.monsterSlug or "Monster")
            :gsub("[^%w]+", "_"):gsub("^_+", ""):gsub("_+$", "")
        if name == "" then
            name = "Monster"
        end
        local shortId = tostring(data.spawnId or "spawn"):gsub("^spawn%-", ""):sub(1, 8)
        return string.format("%s_%s", name, shortId)
    end

    local function createMonsterSpawnMarker(data: any, markerState: string, actorKind: string?): Model
        local spawnId = tostring(data.spawnId or "")
        if not spawnId:match("^spawn%-%w[%w%-]+$") then
            error("Monster Spawn command has invalid spawnId")
        end
        local preview = markerState == "preview"
        local kind = if actorKind == "npc" then "npc" else "monster"
        local folder = monsterSpawnMarkerFolder(kind)
        for _, child in ipairs(folder:GetChildren()) do
            if child:IsA("Model") then
                local registeredCopy = not preview and tostring(child:GetAttribute("SpawnId") or "") == spawnId
                local previewCopy = tostring(child:GetAttribute("PreviewForSpawnId") or "") == spawnId
                if registeredCopy or previewCopy then
                    child:Destroy()
                end
            end
        end

        local world = monsterSpawnMarkerCFrame(data.position, data.yawDegrees)
        local color = preview and Color3.fromRGB(255, 111, 97) or Color3.fromRGB(66, 214, 177)
        local marker = Instance.new("Model")
        marker.Name = monsterSpawnMarkerName(data)
        marker:SetAttribute(if kind == "npc" then "Game1NpcSpawnMarker" else "Game1MonsterSpawnMarker", true)
        marker:SetAttribute("EntityKind", kind)
        marker:SetAttribute("SpawnState", markerState)
        marker:SetAttribute("SpawnId", preview and "" or spawnId)
        if preview then
            marker:SetAttribute("PreviewForSpawnId", spawnId)
        end
        marker:SetAttribute(if kind == "npc" then "NpcSlug" else "MonsterSlug", tostring(data.monsterSlug or ""))
        marker:SetAttribute(if kind == "npc" then "NpcName" else "MonsterName", tostring(data.monsterName or ""))
        marker:SetAttribute("MapKey", tostring(data.mapKey or "main"))
        marker:SetAttribute("PlaceId", tonumber(data.placeId) or game.PlaceId)
        marker:SetAttribute("YawDegrees", tonumber(data.yawDegrees) or 0)
        marker:SetAttribute("SpawnRadius", tonumber(data.spawnRadius) or 0)
        marker:SetAttribute("MaxAlive", tonumber(data.maxAlive) or 1)
        marker:SetAttribute("Enabled", data.enabled ~= false)
        marker.Parent = folder

        local point = safeMonsterSpawnMarkerPart(marker, "Point", Vector3.new(0.12, 2.2, 2.2), world * CFrame.Angles(0, 0, math.rad(90)), color, 0.18)
        point.Shape = Enum.PartType.Cylinder
        safeMonsterSpawnMarkerPart(marker, "Direction", Vector3.new(0.22, 0.12, 3.2), world * CFrame.new(0, 0.18, -1.6), color, 0.12)
        local radius = math.max(0, tonumber(data.spawnRadius) or 0)
        if radius > 0.01 then
            local area = safeMonsterSpawnMarkerPart(marker, "Radius", Vector3.new(0.06, radius * 2, radius * 2), world * CFrame.Angles(0, 0, math.rad(90)), color, 0.84)
            area.Shape = Enum.PartType.Cylinder
        end

        local billboard = Instance.new("BillboardGui")
        billboard.Name = "Label"
        billboard.Adornee = point
        billboard.AlwaysOnTop = true
        billboard.LightInfluence = 0
        billboard.Size = UDim2.fromOffset(250, 52)
        billboard.StudsOffsetWorldSpace = Vector3.new(0, 3.2, 0)
        billboard.Parent = marker
        local text = Instance.new("TextLabel")
        text.BackgroundColor3 = Color3.fromRGB(17, 24, 33)
        text.BackgroundTransparency = 0.08
        text.BorderSizePixel = 0
        text.Size = UDim2.fromScale(1, 1)
        text.Font = Enum.Font.GothamSemibold
        text.TextColor3 = Color3.fromRGB(246, 248, 251)
        text.TextSize = 14
        text.TextWrapped = true
        text.Text = string.format("%s\n%s · max %d%s", tostring(data.monsterName or data.monsterSlug or "Monster"), tostring(data.spawnId or ""), tonumber(data.maxAlive) or 1, preview and " · PREVIEW" or "")
        text.Parent = billboard
        local corner = Instance.new("UICorner")
        corner.CornerRadius = UDim.new(0, 7)
        corner.Parent = text

        marker.PrimaryPart = point
        if preview and kind == "npc" then
            -- Only the unregistered, short-lived draft holds a rendered NPC.
            -- Registered markers remain lightweight regardless of population size.
            local attached, attachError = pcall(function()
                NpcSpawnPreview.Attach(ServerStorage, marker, tostring(data.monsterSlug or ""))
                NpcSpawnPreview.Move(marker, world.Position, tonumber(data.yawDegrees) or 0)
            end)
            if not attached then
                marker:Destroy()
                error(attachError)
            end
        end
        Selection:Set({ marker })
        return marker
    end

    local function moveMonsterSpawnMarker(marker: Model, position: Vector3, yawDegrees: number)
        local world = monsterSpawnMarkerCFrame({ x = position.X, y = position.Y, z = position.Z }, yawDegrees)
        marker:SetAttribute("YawDegrees", yawDegrees)
        NpcSpawnPreview.Move(marker, position, yawDegrees)
        local point = marker:FindFirstChild("Point")
        if point and point:IsA("BasePart") then
            point.CFrame = world * CFrame.Angles(0, 0, math.rad(90))
        end
        local direction = marker:FindFirstChild("Direction")
        if direction and direction:IsA("BasePart") then
            direction.CFrame = world * CFrame.new(0, 0.18, -1.6)
        end
        local radius = marker:FindFirstChild("Radius")
        if radius and radius:IsA("BasePart") then
            radius.CFrame = world * CFrame.Angles(0, 0, math.rad(90))
        end
    end

    local function monsterSpawnCameraYaw(): number
        local camera = Workspace.CurrentCamera
        local look = camera and camera.CFrame.LookVector or Vector3.new(0, 0, -1)
        return math.deg(math.atan2(-look.X, -look.Z)) % 360
    end

    local function monsterSpawnPlacementResult(data: any): any
        local expectedPlaceId = tonumber(data.placeId) or 0
        if expectedPlaceId > 0 and game.PlaceId > 0 and expectedPlaceId ~= game.PlaceId then
            error(string.format("Open PlaceId %d does not match Spawn PlaceId %d", game.PlaceId, expectedPlaceId))
        end

        if tostring(data.entityKind or "monster") == "npc" then
            return NpcSpawnPlacement.Place({
                plugin = plugin,
                Workspace = Workspace,
                UserInputService = UserInputService,
                data = data,
                cameraYaw = monsterSpawnCameraYaw,
                createMarker = createMonsterSpawnMarker,
                moveMarker = moveMonsterSpawnMarker,
            })
        end

        local mouse = plugin:GetMouse()
        local initial = data.position
        local startPosition = Vector3.new(0, 0, 0)
        if typeof(initial) == "table" and tonumber(initial.x) and tonumber(initial.y) and tonumber(initial.z) then
            startPosition = Vector3.new(tonumber(initial.x), tonumber(initial.y), tonumber(initial.z))
        elseif mouse.Target then
            startPosition = mouse.Hit.Position
        end
        local yaw = monsterSpawnCameraYaw()
        data.position = { x = startPosition.X, y = startPosition.Y, z = startPosition.Z }
        data.yawDegrees = yaw
        data.placeId = game.PlaceId
        local preview = createMonsterSpawnMarker(data, "preview", tostring(data.entityKind or "monster"))
        local finished = false
        local cancelled = false
        local chosenPosition = startPosition
        local targetName = ""

        plugin:Activate(true)
        local moveConnection = mouse.Move:Connect(function()
            if mouse.Target then
                chosenPosition = mouse.Hit.Position
                yaw = monsterSpawnCameraYaw()
                moveMonsterSpawnMarker(preview, chosenPosition, yaw)
            end
        end)
        local clickConnection = mouse.Button1Down:Connect(function()
            if mouse.Target then
                chosenPosition = mouse.Hit.Position
                targetName = mouse.Target:GetFullName()
                moveMonsterSpawnMarker(preview, chosenPosition, yaw)
                finished = true
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
            preview:Destroy()
            error(cancelled and "Monster Spawn placement was cancelled" or "Monster Spawn placement timed out")
        end
        return {
            position = { x = chosenPosition.X, y = chosenPosition.Y, z = chosenPosition.Z },
            yawDegrees = yaw,
            target = targetName,
            markerPath = preview:GetFullName(),
        }
    end

    local function handleMonsterSpawn(data: any)
        local kind = tostring(data.entityKind or "monster")
        local result = {
            command = "monster-spawn",
            project = "game1",
            schemaVersion = 1,
            action = tostring(data.action or ""),
            operationId = tostring(data.operationId or ""),
            spawnId = tostring(data.spawnId or ""),
            placeId = game.PlaceId,
            universeId = game.GameId,
            placeName = game.Name,
            mapKey = tostring(data.mapKey or "main"),
        }
        local ok, operationError = xpcall(function()
            if tostring(data.project or "") ~= "game1" or tonumber(data.schemaVersion) ~= 1 or (kind ~= "monster" and kind ~= "npc") then
                error("invalid game1 actor spawn command")
            end
            local action = tostring(data.action or "")
            if action == "place" then
                local placed = monsterSpawnPlacementResult(data)
                for key, value in pairs(placed) do
                    result[key] = value
                end
            elseif action == "upsert" then
                local expectedPlaceId = tonumber(data.placeId) or 0
                if expectedPlaceId > 0 and game.PlaceId > 0 and expectedPlaceId ~= game.PlaceId then
                    error(string.format("Open PlaceId %d does not match Spawn PlaceId %d", game.PlaceId, expectedPlaceId))
                end
                local marker = createMonsterSpawnMarker(data, "registered", kind)
                result.markerPath = marker:GetFullName()
                result.synchronized = true
            elseif action == "select" then
                local marker = findMonsterSpawnMarker(tostring(data.spawnId or ""), kind)
                if not marker then
                    error("registered Monster Spawn marker was not found in Studio")
                end
                Selection:Set({ marker })
                local root = marker.PrimaryPart
                local camera = Workspace.CurrentCamera
                if root and camera then
                    camera.CFrame = CFrame.lookAt(root.Position + Vector3.new(9, 7, 9), root.Position)
                end
                result.markerPath = marker:GetFullName()
                result.synchronized = true
            elseif action == "delete" then
                local spawnId = tostring(data.spawnId or "")
                local marker = findMonsterSpawnMarker(spawnId, kind)
                if marker then
                    marker:Destroy()
                end
                for _, child in ipairs(monsterSpawnMarkerFolder(kind):GetChildren()) do
                    if child:IsA("Model") and tostring(child:GetAttribute("PreviewForSpawnId") or "") == spawnId then
                        child:Destroy()
                    end
                end
                result.deleted = marker ~= nil
                result.synchronized = true
            elseif action == "sync" then
                local folder = monsterSpawnMarkerFolder(kind)
                for _, child in ipairs(folder:GetChildren()) do
                    if child:IsA("Model") and child:GetAttribute(if kind == "npc" then "Game1NpcSpawnMarker" else "Game1MonsterSpawnMarker") == true then
                        child:Destroy()
                    end
                end
                local created = 0
                local skipped = 0
                local syncedSpawnIds = {}
                for _, record in ipairs(typeof(data.records) == "table" and data.records or {}) do
                    local recordPlaceId = tonumber(record.placeId) or 0
                    if recordPlaceId == 0 or game.PlaceId == 0 or recordPlaceId == game.PlaceId then
                        createMonsterSpawnMarker(record, "registered", kind)
                        created += 1
                        table.insert(syncedSpawnIds, tostring(record.spawnId or ""))
                    else
                        skipped += 1
                    end
                end
                result.synchronized = true
                result.created = created
                result.skipped = skipped
                result.syncedSpawnIds = syncedSpawnIds
            else
                error("unsupported Monster Spawn action: " .. action)
            end
        end, debug.traceback)

        if not ok then
            result.error = tostring(operationError)
            warn("[game1 plugin] Monster Spawn command failed: " .. tostring(operationError))
        end
        local postOk, postError = pcall(postMonsterSpawnResult, result)
        if not postOk then
            warn("[game1 plugin] failed to report Monster Spawn result: " .. tostring(postError))
        end
    end


    return handleMonsterSpawn
end

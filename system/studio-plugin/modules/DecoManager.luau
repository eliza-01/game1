local DecoAssetLoader = require(script.Parent.DecoAssetLoader)
local DecoPlacement = require(script.Parent.DecoPlacement)
local DecoTransform = require(script.Parent.DecoTransform)
local DecoPlacedAssetSync = require(script.Parent.DecoPlacedAssetSync)

local DecoManager = {}
DecoManager.__index = DecoManager

local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building" }
local CATEGORY_LABELS = {
    tree = "Trees",
    bush = "Bushes",
    rock = "Rocks",
    light = "Lights",
    fence = "Fences",
    decoration = "Decorations",
    ladder = "Ladders",
    flower = "Flowers",
    building = "Buildings",
}

local function newLabel(parent: Instance, text: string, size: UDim2, position: UDim2, textSize: number, bold: boolean?): TextLabel
    local label = Instance.new("TextLabel")
    label.BackgroundTransparency = 1
    label.TextColor3 = Color3.fromRGB(232, 239, 244)
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.TextYAlignment = Enum.TextYAlignment.Center
    label.Font = if bold then Enum.Font.GothamBold else Enum.Font.Gotham
    label.TextSize = textSize
    label.Text = text
    label.Size = size
    label.Position = position
    label.Parent = parent
    return label
end

local function newButton(parent: Instance, text: string, size: UDim2, position: UDim2): TextButton
    local button = Instance.new("TextButton")
    button.AutoButtonColor = true
    button.BackgroundColor3 = Color3.fromRGB(37, 45, 55)
    button.BorderSizePixel = 0
    button.TextColor3 = Color3.fromRGB(232, 239, 244)
    button.Font = Enum.Font.GothamSemibold
    button.TextSize = 13
    button.Text = text
    button.Size = size
    button.Position = position
    button.Parent = parent
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 7)
    corner.Parent = button
    return button
end

local function prepareViewportModel(model: Model)
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
        end
    end
end

function DecoManager.new(config: any)
    local self = setmetatable({}, DecoManager)
    self.plugin = config.plugin
    self.toolbar = config.toolbar
    self.HttpService = config.HttpService
    self.AssetService = config.AssetService
    self.Workspace = config.Workspace
    self.ChangeHistoryService = config.ChangeHistoryService
    self.UserInputService = config.UserInputService
    self.registry = nil
    self.category = "tree"
    self.index = 1
    self.currentRow = nil
    self.template = nil
    self.preview = nil
    self.loader = DecoAssetLoader.new({
        HttpService = self.HttpService,
        AssetService = self.AssetService,
        agentBaseUrl = config.agentBaseUrl,
        agentToken = config.agentToken,
    })
    self.placement = DecoPlacement.new({
        plugin = self.plugin,
        Workspace = self.Workspace,
        HttpService = self.HttpService,
        ChangeHistoryService = self.ChangeHistoryService,
    })
    self.agentBaseUrl = config.agentBaseUrl
    self.agentToken = config.agentToken
    self:_buildUI()
    self:_wire()
    return self
end

function DecoManager:_buildUI()
    local info = DockWidgetPluginGuiInfo.new(
        Enum.InitialDockState.Right,
        false,
        false,
        390,
        720,
        330,
        690
    )
    self.widget = self.plugin:CreateDockWidgetPluginGui("Game1DecoManager_v1", info)
    self.widget.Title = "game1 · DecoManager"

    local root = Instance.new("Frame")
    root.BackgroundColor3 = Color3.fromRGB(17, 24, 33)
    root.BorderSizePixel = 0
    root.Size = UDim2.fromScale(1, 1)
    root.Parent = self.widget

    newLabel(root, "DECOMANAGER", UDim2.new(1, -24, 0, 22), UDim2.new(0, 12, 0, 10), 11, true).TextColor3 = Color3.fromRGB(66, 214, 177)
    self.title = newLabel(root, "Location assets", UDim2.new(1, -24, 0, 28), UDim2.new(0, 12, 0, 31), 18, true)

    local categoryHost = Instance.new("Frame")
    categoryHost.BackgroundTransparency = 1
    categoryHost.Size = UDim2.new(1, -24, 0, 106)
    categoryHost.Position = UDim2.new(0, 12, 0, 68)
    categoryHost.Parent = root
    self.categoryButtons = {}
    for index, category in ipairs(CATEGORY_ORDER) do
        local column = (index - 1) % 4
        local row = math.floor((index - 1) / 4)
        local button = newButton(categoryHost, CATEGORY_LABELS[category], UDim2.new(1 / 4, -5, 0, 32), UDim2.new(column / 4, 0, 0, row * 36))
        button.TextSize = 11
        self.categoryButtons[category] = button
    end

    local navHost = Instance.new("Frame")
    navHost.BackgroundTransparency = 1
    navHost.Size = UDim2.new(1, -24, 0, 40)
    navHost.Position = UDim2.new(0, 12, 0, 181)
    navHost.Parent = root
    self.previous = newButton(navHost, "‹", UDim2.new(0, 44, 1, 0), UDim2.new(0, 0, 0, 0))
    self.next = newButton(navHost, "›", UDim2.new(0, 44, 1, 0), UDim2.new(1, -44, 0, 0))
    self.counter = newLabel(navHost, "0 / 0", UDim2.new(1, -100, 1, 0), UDim2.new(0, 50, 0, 0), 12, false)
    self.counter.TextXAlignment = Enum.TextXAlignment.Center

    self.viewport = Instance.new("ViewportFrame")
    self.viewport.BackgroundColor3 = Color3.fromRGB(11, 16, 22)
    self.viewport.BorderSizePixel = 0
    self.viewport.Size = UDim2.new(1, -24, 0, 276)
    self.viewport.Position = UDim2.new(0, 12, 0, 229)
    self.viewport.Ambient = Color3.fromRGB(180, 180, 180)
    self.viewport.LightColor = Color3.fromRGB(255, 255, 255)
    self.viewport.LightDirection = Vector3.new(-1, -1, -1)
    self.viewport.Parent = root
    local viewportCorner = Instance.new("UICorner")
    viewportCorner.CornerRadius = UDim.new(0, 8)
    viewportCorner.Parent = self.viewport
    self.world = Instance.new("WorldModel")
    self.world.Name = "DecoPreviewWorld"
    self.world.Parent = self.viewport
    self.camera = Instance.new("Camera")
    self.camera.Name = "DecoPreviewCamera"
    self.camera.FieldOfView = 35
    self.camera.Parent = self.viewport
    self.viewport.CurrentCamera = self.camera
    self.empty = newLabel(self.viewport, "No published assets in this category", UDim2.new(1, -28, 0, 30), UDim2.new(0, 14, 0.5, -15), 12, false)
    self.empty.TextColor3 = Color3.fromRGB(143, 161, 173)
    self.empty.TextXAlignment = Enum.TextXAlignment.Center
    self.cameraTarget = Vector3.zero
    self.cameraDistance = 8
    self.cameraMinDistance = 1
    self.cameraMaxDistance = 40
    self.cameraYaw = math.rad(35)
    self.cameraPitch = math.rad(18)
    self.previewDragging = false

    self.assetName = newLabel(root, "—", UDim2.new(1, -24, 0, 24), UDim2.new(0, 12, 0, 514), 14, true)
    self.assetMeta = newLabel(root, "published registry", UDim2.new(1, -24, 0, 20), UDim2.new(0, 12, 0, 538), 10, false)
    self.assetMeta.TextColor3 = Color3.fromRGB(143, 161, 173)

    self.place = newButton(root, "Place", UDim2.new(0.5, -17, 0, 38), UDim2.new(0, 12, 0, 568))
    self.place.BackgroundColor3 = Color3.fromRGB(66, 214, 177)
    self.place.TextColor3 = Color3.fromRGB(6, 39, 31)
    self.save = newButton(root, "Save Assets Data", UDim2.new(0.5, -17, 0, 38), UDim2.new(0.5, 5, 0, 568))
    self.refresh = newButton(root, "Refresh registry", UDim2.new(1, -24, 0, 32), UDim2.new(0, 12, 0, 614))
    self.status = newLabel(root, "Open DecoManager to load published assets.", UDim2.new(1, -24, 0, 38), UDim2.new(0, 12, 0, 650), 10, false)
    self.status.TextColor3 = Color3.fromRGB(143, 161, 173)
    self.status.TextWrapped = true

    self.widget:GetPropertyChangedSignal("AbsoluteSize"):Connect(function()
        -- Dock widgets can be shorter than the preferred height. Keep the status visible at the bottom.
        local height = self.widget.AbsoluteSize.Y
        if height > 0 then
            self.status.Position = UDim2.new(0, 12, 1, -42)
        end
    end)
end

function DecoManager:_rows(): { any }
    local rows = {}
    if self.registry and type(self.registry.items) == "table" then
        for _, row in ipairs(self.registry.items) do
            if tostring(row.category or "") == self.category and tostring(row.status or "") == "PUBLISHED" then
                if tonumber(row.model_asset_id) and tonumber(row.texture_asset_id) then
                    table.insert(rows, row)
                end
            end
        end
    end
    table.sort(rows, function(left, right)
        return tostring(left.name_en or left.slug) < tostring(right.name_en or right.slug)
    end)
    return rows
end

function DecoManager:_setStatus(message: string)
    self.status.Text = message
end

function DecoManager:_clearPreview()
    if self.preview then
        self.preview:Destroy()
        self.preview = nil
    end
    if self.template then
        self.template:Destroy()
        self.template = nil
    end
    for _, child in ipairs(self.world:GetChildren()) do
        child:Destroy()
    end
    self.currentRow = nil
    self.empty.Visible = true
    self.assetName.Text = "—"
    self.assetMeta.Text = CATEGORY_LABELS[self.category]
    self.place.Active = false
    self.place.AutoButtonColor = false
    self.place.BackgroundColor3 = Color3.fromRGB(49, 57, 67)
    self.place.TextColor3 = Color3.fromRGB(143, 161, 173)
end

function DecoManager:_updatePreviewCamera()
    self.cameraDistance = math.clamp(self.cameraDistance, self.cameraMinDistance, self.cameraMaxDistance)
    self.cameraPitch = math.clamp(self.cameraPitch, math.rad(-70), math.rad(70))
    local cosPitch = math.cos(self.cameraPitch)
    local offset = Vector3.new(
        math.sin(self.cameraYaw) * cosPitch,
        math.sin(self.cameraPitch),
        math.cos(self.cameraYaw) * cosPitch
    ) * self.cameraDistance
    self.camera.CFrame = CFrame.lookAt(self.cameraTarget + offset, self.cameraTarget, Vector3.yAxis)
end

function DecoManager:_framePreview(model: Model)
    model:PivotTo(DecoTransform.previewPivot(model))
    local boundsCFrame, boundsSize = model:GetBoundingBox()
    local radius = math.max(boundsSize.X, boundsSize.Y, boundsSize.Z, 1)
    self.cameraTarget = boundsCFrame.Position
    self.cameraMinDistance = math.max(radius * 0.55, 0.75)
    self.cameraMaxDistance = math.max(radius * 5, self.cameraMinDistance + 1)
    self.cameraDistance = math.clamp(radius * 1.9, self.cameraMinDistance, self.cameraMaxDistance)
    self.cameraYaw = math.rad(35)
    self.cameraPitch = math.rad(15)
    self:_updatePreviewCamera()
end

function DecoManager:_showCurrent()
    self.placement:cancel()
    local rows = self:_rows()
    if #rows == 0 then
        self.index = 1
        self.counter.Text = "0 / 0"
        self:_clearPreview()
        self:_setStatus("No published " .. string.lower(CATEGORY_LABELS[self.category]) .. ". Publish one in Asset Manager.")
        return
    end
    self.index = math.clamp(self.index, 1, #rows)
    local row = rows[self.index]
    self.counter.Text = tostring(self.index) .. " / " .. tostring(#rows)
    self:_clearPreview()
    self:_setStatus("Loading " .. tostring(row.name_en or row.slug) .. "…")
    local ok, result = pcall(function()
        return self.loader:loadPublished(row)
    end)
    if not ok then
        self:_setStatus("Preview failed · " .. tostring(result))
        warn("[game1 DecoManager] " .. tostring(result))
        return
    end
    self.template = result
    self.currentRow = row
    self.preview = result:Clone()
    prepareViewportModel(self.preview)
    self.preview.Parent = self.world
    self:_framePreview(self.preview)
    self.empty.Visible = false
    self.assetName.Text = tostring(row.name_en or row.slug)
    self.assetMeta.Text = CATEGORY_LABELS[self.category] .. " · model " .. tostring(row.model_asset_id) .. " · texture " .. tostring(row.texture_asset_id)
    self.place.Active = true
    self.place.AutoButtonColor = true
    self.place.BackgroundColor3 = Color3.fromRGB(66, 214, 177)
    self.place.TextColor3 = Color3.fromRGB(6, 39, 31)
    self:_setStatus("Ready · Place starts surface-snapped placement in the 3D viewport.")
end

function DecoManager:_setCategory(category: string)
    if CATEGORY_LABELS[category] == nil then
        return
    end
    self.category = category
    self.index = 1
    for key, button in pairs(self.categoryButtons) do
        button.BackgroundColor3 = if key == category then Color3.fromRGB(49, 112, 96) else Color3.fromRGB(37, 45, 55)
    end
    self:_showCurrent()
end

function DecoManager:refreshRegistry()
    self:_setStatus("Refreshing Location Assets registry…")
    local ok, result = pcall(function()
        return self.loader:fetchRegistry()
    end)
    if not ok then
        self.registry = nil
        self:_clearPreview()
        self:_setStatus("Asset Manager unavailable · " .. tostring(result))
        return
    end
    self.registry = result
    local syncResult = DecoPlacedAssetSync.RefreshTextures(self.Workspace, result)
    if syncResult.parts > 0 then
        self.ChangeHistoryService:SetWaypoint("Refresh Deco Asset Textures")
    end
    self:_setCategory(self.category)
    if syncResult.parts > 0 then
        self:_setStatus(("Registry refreshed · updated texture on %d placed asset(s) / %d MeshPart(s)"):format(
            syncResult.models,
            syncResult.parts
        ))
    end
end

function DecoManager:_placeCurrent()
    if self.template == nil or self.currentRow == nil then
        return
    end
    self.placement:start(self.template, self.currentRow, function(message)
        self:_setStatus(message)
    end)
end

function DecoManager:_postLayout(records: { any }): any
    local response = self.HttpService:RequestAsync({
        Url = self.agentBaseUrl .. "/api/location-assets/layout",
        Method = "POST",
        Headers = {
            ["X-Control-Token"] = self.agentToken,
            ["Content-Type"] = "application/json",
        },
        Body = self.HttpService:JSONEncode({
            schemaVersion = 1,
            project = "game1",
            placeId = game.PlaceId,
            placeName = game.Name,
            records = records,
        }),
    })
    if not response.Success then
        error(("Asset Manager backup HTTP %d: %s"):format(response.StatusCode, response.Body))
    end
    return self.HttpService:JSONDecode(response.Body)
end

function DecoManager:_saveAssetsData()
    self.placement:cancel()
    local records = self.placement:serialize()
    self:_setStatus(("Saving %d placed asset(s)…"):format(#records))
    local ok, backup = pcall(function()
        return self:_postLayout(records)
    end)
    if not ok then
        self:_setStatus("Assets data save failed · " .. tostring(backup))
        warn("[game1 DecoManager] " .. tostring(backup))
        return
    end
    local studioSave = backup.studioSave or {}
    if studioSave.requested == true then
        self:_setStatus(("Saved · %d asset(s) · %s · Studio save requested"):format(#records, tostring(backup.backupPath or "backup")))
    else
        self:_setStatus(("Backup saved (%s), but Studio save was not requested"):format(tostring(backup.backupPath or "backup")))
    end
end

function DecoManager:_wire()
    self.button = self.toolbar:CreateButton(
        "Game1DecoManager",
        "Browse and place published game1 location assets",
        "",
        "DecoManager"
    )
    self.button.ClickableWhenViewportHidden = true
    self.button.Click:Connect(function()
        self.widget.Enabled = not self.widget.Enabled
    end)
    self.widget:GetPropertyChangedSignal("Enabled"):Connect(function()
        self.button:SetActive(self.widget.Enabled)
        if self.widget.Enabled then
            task.defer(function()
                self:refreshRegistry()
            end)
        else
            self.placement:cancel()
        end
    end)
    for category, categoryButton in pairs(self.categoryButtons) do
        categoryButton.MouseButton1Click:Connect(function()
            self:_setCategory(category)
        end)
    end
    self.previous.MouseButton1Click:Connect(function()
        local rows = self:_rows()
        if #rows == 0 then return end
        self.index = ((self.index - 2) % #rows) + 1
        self:_showCurrent()
    end)
    self.next.MouseButton1Click:Connect(function()
        local rows = self:_rows()
        if #rows == 0 then return end
        self.index = (self.index % #rows) + 1
        self:_showCurrent()
    end)
    self.viewport.MouseLeave:Connect(function()
        self.previewDragging = false
    end)
    self.viewport.InputBegan:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 and self.preview ~= nil then
            self.previewDragging = true
        end
    end)
    self.viewport.InputChanged:Connect(function(input)
        if self.preview == nil then
            return
        end
        if input.UserInputType == Enum.UserInputType.MouseMovement and self.previewDragging then
            self.cameraYaw -= input.Delta.X * 0.010
            self.cameraPitch -= input.Delta.Y * 0.008
            self:_updatePreviewCamera()
        elseif input.UserInputType == Enum.UserInputType.MouseWheel then
            local wheel = input.Position.Z
            if math.abs(wheel) > 0.001 then
                local step = math.max(self.cameraDistance * 0.12, 0.15)
                self.cameraDistance -= wheel * step
                self:_updatePreviewCamera()
            end
        end
    end)
    self.viewport.InputEnded:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 then
            self.previewDragging = false
        end
    end)
    self.UserInputService.InputEnded:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 then
            self.previewDragging = false
        end
    end)
    self.place.MouseButton1Click:Connect(function()
        self:_placeCurrent()
    end)
    self.refresh.MouseButton1Click:Connect(function()
        self:refreshRegistry()
    end)
    self.save.MouseButton1Click:Connect(function()
        self:_saveAssetsData()
    end)
    self.plugin.Deactivation:Connect(function()
        self.placement:cancel()
    end)
    self.plugin.Unloading:Connect(function()
        self.placement:cancel()
        self:_clearPreview()
    end)
    self:_setCategory("tree")
end

return DecoManager

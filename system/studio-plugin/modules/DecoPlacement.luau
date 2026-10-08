local DecoPlacement = {}
DecoPlacement.__index = DecoPlacement

local ROOT_NAME = "Game1DecoAssets"
local CATEGORY_FOLDERS = {
    tree = "Trees",
    bush = "Bushes",
    rock = "Rocks",
    light = "Lights",
    fence = "Fences",
    decoration = "Decorations",
}

local function prepareGhost(model: Model)
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
            descendant.CastShadow = false
            descendant.Transparency = math.max(descendant.Transparency, 0.45)
        end
    end
end

local function preparePlaced(model: Model)
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanTouch = false
        end
    end
end

local function localSupportOffset(model: Model): number
    local pivot = model:GetPivot()
    local minimumY = math.huge
    local hasPart = false
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            hasPart = true
            local localPart = pivot:ToObjectSpace(descendant.CFrame)
            local half = descendant.Size * 0.5
            for _, x in ipairs({ -1, 1 }) do
                for _, y in ipairs({ -1, 1 }) do
                    for _, z in ipairs({ -1, 1 }) do
                        local point = localPart:PointToWorldSpace(Vector3.new(half.X * x, half.Y * y, half.Z * z))
                        minimumY = math.min(minimumY, point.Y)
                    end
                end
            end
        end
    end
    if not hasPart then
        error("location asset model contains no BasePart geometry")
    end
    return math.max(0, -minimumY)
end

local function orientationForSurface(normal: Vector3, cameraLook: Vector3): CFrame
    local up = if normal.Magnitude > 0.001 then normal.Unit else Vector3.yAxis
    local forward = cameraLook - up * cameraLook:Dot(up)
    if forward.Magnitude < 0.01 then
        local fallback = if math.abs(up.Y) < 0.95 then Vector3.yAxis else Vector3.zAxis
        forward = fallback - up * fallback:Dot(up)
    end
    forward = forward.Unit
    return CFrame.lookAt(Vector3.zero, forward, up)
end

function DecoPlacement.new(config: any)
    local self = setmetatable({
        plugin = config.plugin,
        Workspace = config.Workspace,
        HttpService = config.HttpService,
        ChangeHistoryService = config.ChangeHistoryService,
        mouse = config.plugin:GetMouse(),
        sourceTemplate = nil,
        row = nil,
        ghost = nil,
        supportOffset = 0,
        moveConnection = nil,
        clickConnection = nil,
        statusCallback = nil,
        committing = false,
    }, DecoPlacement)
    return self
end

function DecoPlacement:_root(): Folder
    local root = self.Workspace:FindFirstChild(ROOT_NAME)
    if root and not root:IsA("Folder") then
        error("Workspace." .. ROOT_NAME .. " exists but is not a Folder")
    end
    if root == nil then
        root = Instance.new("Folder")
        root.Name = ROOT_NAME
        root.Parent = self.Workspace
    end
    return root :: Folder
end

function DecoPlacement:_categoryFolder(category: string): Folder
    local root = self:_root()
    local name = CATEGORY_FOLDERS[category]
    if name == nil then
        error("unsupported deco category: " .. category)
    end
    local folder = root:FindFirstChild(name)
    if folder and not folder:IsA("Folder") then
        error(root:GetFullName() .. "." .. name .. " exists but is not a Folder")
    end
    if folder == nil then
        folder = Instance.new("Folder")
        folder.Name = name
        folder.Parent = root
    end
    return folder :: Folder
end

function DecoPlacement:_status(message: string)
    if self.statusCallback then
        self.statusCallback(message)
    end
end

function DecoPlacement:_raycast(): RaycastResult?
    local unitRay = self.mouse.UnitRay
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    local excluded = {}
    if self.ghost ~= nil then
        table.insert(excluded, self.ghost)
    end
    local authoring = self.Workspace:FindFirstChild("Game1Authoring")
    if authoring ~= nil then
        table.insert(excluded, authoring)
    end
    params.FilterDescendantsInstances = excluded
    params.IgnoreWater = false
    return self.Workspace:Raycast(unitRay.Origin, unitRay.Direction * 10000, params)
end

function DecoPlacement:_updateGhost()
    if self.ghost == nil then
        return
    end
    local hit = self:_raycast()
    if hit == nil then
        self:_status("Placement · point at a surface")
        return
    end
    local camera = self.Workspace.CurrentCamera
    local cameraLook = if camera then camera.CFrame.LookVector else Vector3.new(0, 0, -1)
    local orientation = orientationForSurface(hit.Normal, cameraLook)
    local targetPosition = hit.Position + hit.Normal.Unit * self.supportOffset
    self.ghost:PivotTo(CFrame.new(targetPosition) * orientation)
    self:_status("Placement · click to place on " .. hit.Instance:GetFullName())
end

function DecoPlacement:_detachSession(): Model?
    if self.moveConnection then
        self.moveConnection:Disconnect()
        self.moveConnection = nil
    end
    if self.clickConnection then
        self.clickConnection:Disconnect()
        self.clickConnection = nil
    end
    local ghost = self.ghost
    self.ghost = nil
    self.sourceTemplate = nil
    self.row = nil
    self.supportOffset = 0
    return ghost
end

function DecoPlacement:cancel()
    local ghost = self:_detachSession()
    if ghost ~= nil then
        ghost:Destroy()
    end
    self.committing = false
end

function DecoPlacement:_commit()
    if self.committing or self.ghost == nil or self.sourceTemplate == nil or self.row == nil then
        return
    end
    self.committing = true

    local ghost = self.ghost
    local sourceTemplate = self.sourceTemplate
    local row = self.row
    local statusCallback = self.statusCallback
    local pivot = ghost:GetPivot()

    local placed = sourceTemplate:Clone()
    preparePlaced(placed)
    local instanceId = self.HttpService:GenerateGUID(false)
    placed.Name = tostring(row.slug or "deco") .. "__" .. string.sub(instanceId, 1, 8)
    placed:SetAttribute("Game1DecoAsset", true)
    placed:SetAttribute("Game1DecoInstanceId", instanceId)
    placed:SetAttribute("Game1DecoAssetSlug", tostring(row.slug or ""))
    placed:SetAttribute("Game1DecoCategory", tostring(row.category or ""))
    placed:SetAttribute("Game1DecoModelAssetId", tostring(row.model_asset_id or ""))
    placed:SetAttribute("Game1DecoTextureAssetId", tostring(row.texture_asset_id or ""))
    placed.Parent = self:_categoryFolder(tostring(row.category or ""))
    placed:PivotTo(pivot)

    -- Detach the session before deactivating the plugin. Deactivation is re-entrant
    -- and must never be able to destroy an instance that the active call still uses.
    local staleGhost = self:_detachSession()
    if staleGhost ~= nil then
        staleGhost:Destroy()
    end
    self.plugin:Deactivate()
    self.ChangeHistoryService:SetWaypoint("Place Deco Asset")

    self.committing = false
    if statusCallback then
        statusCallback("Placed · " .. placed.Name)
    end
end

function DecoPlacement:start(template: Model, row: any, statusCallback: (string) -> ())
    self:cancel()

    -- Activate before creating the new transient session. Studio may fire
    -- Plugin.Deactivation while tool ownership changes; there is nothing fresh to
    -- destroy until Activate has completed.
    self.plugin:Activate(true)

    self.sourceTemplate = template
    self.row = row
    self.statusCallback = statusCallback
    self.supportOffset = localSupportOffset(template)

    local ghost = template:Clone()
    ghost.Name = "Game1DecoPlacementGhost"
    prepareGhost(ghost)
    self.ghost = ghost

    -- Keep the placement preview out of the authored Workspace tree and change
    -- history. Camera descendants still render in Studio and use world CFrames.
    local camera = self.Workspace.CurrentCamera
    ghost.Parent = if camera ~= nil then camera else self.Workspace

    self:_updateGhost()
    self.moveConnection = self.mouse.Move:Connect(function()
        self:_updateGhost()
    end)
    self.clickConnection = self.mouse.Button1Down:Connect(function()
        if self:_raycast() ~= nil then
            self:_updateGhost()
            self:_commit()
        end
    end)
end

function DecoPlacement:serialize(): { any }
    local root = self.Workspace:FindFirstChild(ROOT_NAME)
    if root == nil then
        return {}
    end
    local records = {}
    for _, descendant in ipairs(root:GetDescendants()) do
        if descendant:IsA("Model") and descendant:GetAttribute("Game1DecoAsset") == true then
            local pivot = descendant:GetPivot()
            local cframe = { pivot:GetComponents() }
            local scale = 1
            pcall(function()
                scale = descendant:GetScale()
            end)
            table.insert(records, {
                instanceId = tostring(descendant:GetAttribute("Game1DecoInstanceId") or ""),
                name = descendant.Name,
                slug = tostring(descendant:GetAttribute("Game1DecoAssetSlug") or ""),
                category = tostring(descendant:GetAttribute("Game1DecoCategory") or ""),
                modelAssetId = tostring(descendant:GetAttribute("Game1DecoModelAssetId") or ""),
                textureAssetId = tostring(descendant:GetAttribute("Game1DecoTextureAssetId") or ""),
                cframe = cframe,
                scale = scale,
            })
        end
    end
    table.sort(records, function(left, right)
        return tostring(left.instanceId) < tostring(right.instanceId)
    end)
    return records
end

return DecoPlacement

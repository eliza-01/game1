local DecoTransform = require(script.Parent.DecoTransform)

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
            -- Placement ghosts are anchored, authored decorations are not. Keep the
            -- placed asset editable with the normal Studio transform tools.
            descendant.Anchored = false
            descendant.CanTouch = false
        end
    end
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
        authoredPivotRotation = CFrame.identity,
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
    local normal = if hit.Normal.Magnitude > 0.001 then hit.Normal.Unit else Vector3.yAxis
    local targetPosition = hit.Position + normal * self.supportOffset
    self.ghost:PivotTo(DecoTransform.placementPivot(
        self.authoredPivotRotation,
        targetPosition,
        normal,
        cameraLook
    ))
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
    self.authoredPivotRotation = CFrame.identity
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
    -- Studio placement stores identity, not gameplay policy. Runtime resolves the
    -- current LocationAssetRegistry definition from this stable asset key.
    placed:SetAttribute("Game1DecoInstanceId", instanceId)
    placed:SetAttribute("Game1DecoAssetSlug", tostring(row.slug or ""))
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
    self.supportOffset = DecoTransform.supportOffset(template)
    self.authoredPivotRotation = DecoTransform.authoredPivotRotation(template)

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
        if descendant:IsA("Model") and tostring(descendant:GetAttribute("Game1DecoAssetSlug") or "") ~= "" then
            local pivot = descendant:GetPivot()
            local cframe = { pivot:GetComponents() }
            local scale = 1
            pcall(function()
                scale = descendant:GetScale()
            end)
            table.insert(records, {
                instanceId = tostring(descendant:GetAttribute("Game1DecoInstanceId") or ""),
                name = descendant.Name,
                locationAssetId = tostring(descendant:GetAttribute("Game1DecoAssetSlug") or ""),
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

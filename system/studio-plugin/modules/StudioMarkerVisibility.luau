-- Studio-only presentation toggle. No movement of markers, no metadata edits.
-- Temporary visual overrides are always restored when shown again.
local Visibility = {}
Visibility.__index = Visibility

local SETTING_KEY = "Game1AuthoringMarkersVisible_v1"
local MARKER_TAGS = {"Game1MonsterSpawnMarker", "Game1NpcSpawnMarker", "Game1LocationMarker"}

local function isMarker(instance: Instance): boolean
    if not instance:IsA("Model") then return false end
    for _, name in ipairs(MARKER_TAGS) do
        if instance:GetAttribute(name) == true then return true end
    end
    return false
end

function Visibility.new(plugin: Plugin, toolbar: PluginToolbar, workspace: Workspace)
    local self = setmetatable({
        plugin = plugin, workspace = workspace, connections = {},
        original = setmetatable({}, {__mode = "k"}),
        visible = true,
    }, Visibility)
    local ok, saved = pcall(function() return plugin:GetSetting(SETTING_KEY) end)
    if ok and type(saved) == "boolean" then self.visible = saved end
    self.button = toolbar:CreateButton("Game1AuthoringMarkers", "Show / hide Game1 spawn markers and location boundaries", "", "Markers")
    self.button.ClickableWhenViewportHidden = true
    self.button.Click:Connect(function() self:SetVisible(not self.visible) end)
    self.button:SetActive(self.visible)
    print("[game1][studio-markers] Markers toolbar button registered · M95 UI hotfix")
    table.insert(self.connections, workspace.DescendantAdded:Connect(function(instance)
        -- Works for newly restored/reparented markers and parts created in them,
        -- including restoring overrides when a marker re-enters Workspace while visible.
        task.defer(function()
            if instance.Parent then self:_apply(instance) end
        end)
    end))
    self:_apply(workspace)
    return self
end

function Visibility:_setItem(instance: Instance)
    local property: string? = nil
    local hiddenValue: any = nil
    if instance:IsA("BasePart") then
        -- Per-client visualization override; original published Transparency is untouched.
        property, hiddenValue = "LocalTransparencyModifier", 1
    elseif instance:IsA("BillboardGui") or instance:IsA("SurfaceGui") then
        property, hiddenValue = "Enabled", false
    elseif instance:IsA("Highlight") then
        property, hiddenValue = "Enabled", false
    elseif instance:IsA("SelectionBox") or instance:IsA("SphereHandleAdornment") or instance:IsA("BoxHandleAdornment") then
        property, hiddenValue = "Visible", false
    end
    if not property then return end
    if not self.visible then
        if self.original[instance] == nil then
            local ok, old = pcall(function() return (instance :: any)[property] end)
            if ok then self.original[instance] = {property = property, value = old} end
        end
        pcall(function() (instance :: any)[property] = hiddenValue end)
    else
        local record = self.original[instance]
        if record then
            pcall(function() (instance :: any)[record.property] = record.value end)
            self.original[instance] = nil
        end
    end
end

function Visibility:_apply(instance: Instance)
    local marker: Instance? = instance
    while marker and marker ~= self.workspace and not isMarker(marker) do
        marker = marker.Parent
    end
    if marker ~= nil and isMarker(marker) then
        self:_setItem(instance)
        for _, child in ipairs(instance:GetDescendants()) do self:_setItem(child) end
    elseif instance == self.workspace then
        for _, child in ipairs(self.workspace:GetDescendants()) do
            if isMarker(child) then
                self:_setItem(child)
                for _, descendant in ipairs(child:GetDescendants()) do self:_setItem(descendant) end
            end
        end
    end
end

function Visibility:SetVisible(value: boolean)
    self.visible = value
    self.button:SetActive(value)
    pcall(function() self.plugin:SetSetting(SETTING_KEY, value) end)
    self:_apply(self.workspace)
end

function Visibility:Destroy()
    self:SetVisible(true)
    for _, connection in ipairs(self.connections) do connection:Disconnect() end
    table.clear(self.connections)
end

return table.freeze(Visibility)

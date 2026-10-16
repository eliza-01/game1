-- Studio-only presentation toggle. No movement of markers, no metadata edits.
-- Visibility is re-applied from authored marker defaults after Studio restart.
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
        destroyed = false,
        visible = true,
    }, Visibility)
    local ok, saved = pcall(function() return plugin:GetSetting(SETTING_KEY) end)
    if ok and type(saved) == "boolean" then self.visible = saved end
    self.button = toolbar:CreateButton("Game1AuthoringMarkers", "Show / hide Game1 spawn markers and location boundaries", "", "Markers")
    self.button.ClickableWhenViewportHidden = true
    table.insert(self.connections, self.button.Click:Connect(function() self:SetVisible(not self.visible) end))
    self.button:SetActive(self.visible)
    table.insert(self.connections, plugin.Unloading:Connect(function()
        -- Undo temporary visual overrides before unloading, without replacing
        -- the user's saved show/hide preference for the next Studio session.
        self:Destroy()
    end))
    table.insert(self.connections, workspace.DescendantAdded:Connect(function(instance)
        -- Works for newly restored/reparented markers and parts created in them,
        -- including restoring overrides when a marker re-enters Workspace while visible.
        task.defer(function()
            if not self.destroyed and instance.Parent then self:_apply(instance) end
        end)
    end))
    local count = self:_apply(workspace)
    print(("[game1][studio-markers] toolbar ready · %s · %d marker(s)")
        :format(if self.visible then "shown" else "hidden", count))
    return self
end

-- Markers are created by StudioActorSpawnCommands and LocationCommands.
-- Their visual defaults are LocalTransparencyModifier=0 and Enabled/Visible=true.
-- That fallback is essential: an older plugin instance could save a hidden
-- marker, then forget its in-memory `original` snapshot on Studio restart.
local function visualProperty(instance: Instance): (string?, any, any)
    if instance:IsA("BasePart") then
        return "LocalTransparencyModifier", 1, 0
    elseif instance:IsA("BillboardGui") or instance:IsA("SurfaceGui") then
        return "Enabled", false, true
    elseif instance:IsA("Highlight") then
        return "Enabled", false, true
    elseif instance:IsA("SelectionBox") or instance:IsA("SphereHandleAdornment") or instance:IsA("BoxHandleAdornment") then
        return "Visible", false, true
    end
    return nil, nil, nil
end

function Visibility:_setItem(instance: Instance)
    local property, hiddenValue, defaultVisible = visualProperty(instance)
    if not property then return end
    if not self.visible then
        if self.original[instance] == nil then
            local ok, old = pcall(function() return (instance :: any)[property] end)
            if ok then
                -- Hidden property values cannot be trusted as an original on
                -- startup; normalize them to authored marker defaults.
                self.original[instance] = {
                    property = property,
                    value = if old == hiddenValue then defaultVisible else old,
                }
            end
        end
        pcall(function() (instance :: any)[property] = hiddenValue end)
    else
        local record = self.original[instance]
        local value = if record then record.value else defaultVisible
        pcall(function() (instance :: any)[property] = value end)
        self.original[instance] = nil
    end
end

function Visibility:_apply(instance: Instance): number
    local marker: Instance? = instance
    while marker and marker ~= self.workspace and not isMarker(marker) do
        marker = marker.Parent
    end
    if marker ~= nil and isMarker(marker) then
        self:_setItem(instance)
        for _, child in ipairs(instance:GetDescendants()) do self:_setItem(child) end
        return 1
    elseif instance == self.workspace then
        local count = 0
        for _, child in ipairs(self.workspace:GetDescendants()) do
            if isMarker(child) then
                count += 1
                self:_setItem(child)
                for _, descendant in ipairs(child:GetDescendants()) do self:_setItem(descendant) end
            end
        end
        return count
    end
    return 0
end

function Visibility:SetVisible(value: boolean)
    if self.destroyed then return end
    self.visible = value
    self.button:SetActive(value)
    pcall(function() self.plugin:SetSetting(SETTING_KEY, value) end)
    local count = self:_apply(self.workspace)
    print(("[game1][studio-markers] %s · %d marker(s)")
        :format(if value then "shown" else "hidden", count))
    if count == 0 then
        warn("[game1][studio-markers] no authored marker models in Workspace; "
            .. "check Workspace.Game1Authoring or use Restore markers in Asset Manager "
            .. "(Monster/NPC Population and Locations). In Play, the spawn marker folders are removed by runtime.")
    end
end

function Visibility:Destroy()
    if self.destroyed then return end
    self.destroyed = true
    -- Do not persist 'shown' to plugin settings: the preference survives reload,
    -- but editor-owned marker properties must not remain hidden after unloading.
    self.visible = true
    pcall(function() self:_apply(self.workspace) end)
    for _, connection in ipairs(self.connections) do connection:Disconnect() end
    table.clear(self.connections)
end

return table.freeze(Visibility)

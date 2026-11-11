--!strict
-- Hides editor-only Plot volumes and number markers in running experiences.
-- Does not touch plot folders, authored Houses, or Studio Edit documents.
local Workspace = game:GetService("Workspace")

local Service = {}
local started = false

local function plotIndex(folder: Instance?): number?
    if not folder or not folder:IsA("Folder") then return nil end
    local plots = folder.Parent
    if not plots or plots.Name ~= "Plots" or plots.Parent ~= Workspace then return nil end
    local index = tonumber(folder.Name)
    if not index or index < 1 or index > 50 or math.floor(index) ~= index then return nil end
    return index
end

local function authoredVolume(part: Instance): boolean
    if not part:IsA("BasePart") then return false end
    local index = plotIndex(part.Parent)
    if not index then return false end
    return part.Name == ("plot_%02d_volume"):format(index)
        or part.Name == ("plot_%d_volume"):format(index)
end

local function isMarker(instance: Instance): boolean
    -- A volume (and its numbered child model) is explicitly editor-only.
    local current: Instance? = instance
    while current and current ~= Workspace do
        if authoredVolume(current) then return true end
        current = current.Parent
    end
    -- Compatibility with the original unparented Numbers_1_50 folder.
    local root = Workspace:FindFirstChild("Numbers_1-50")
    local numbers = root and root:FindFirstChild("Numbers_1_50")
    if numbers then
        local child: Instance? = instance
        while child and child.Parent ~= numbers and child ~= Workspace do
            child = child.Parent
        end
        if child and child.Parent == numbers and child:IsA("Model") then
            local index = tonumber(child.Name)
            return index ~= nil and index >= 1 and index <= 50 and math.floor(index) == index
        end
    end
    return false
end

local function hide(instance: Instance)
    if not isMarker(instance) then return end
    if instance:IsA("BasePart") then
        instance.Transparency = 1
        instance.LocalTransparencyModifier = 1
        instance.CanCollide = false
        instance.CanTouch = false
        instance.CanQuery = false
        instance.CastShadow = false
    elseif instance:IsA("BillboardGui") or instance:IsA("SurfaceGui") then
        instance.Enabled = false
    end
end

function Service.Start()
    if started then return end
    started = true
    for _, item in ipairs(Workspace:GetDescendants()) do hide(item) end
    Workspace.DescendantAdded:Connect(hide)
end

return table.freeze(Service)

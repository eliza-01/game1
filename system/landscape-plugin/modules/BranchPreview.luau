-- Temporary Studio overlays: all preview instances live under CoreGui,
-- never inside Workspace or Camera, so saving the Place cannot retain them.
local BranchGeometry = require(script.Parent.BranchGeometry)

local BranchPreview = {}
BranchPreview.__index = BranchPreview

local function segmentFrame(from: Vector3, to: Vector3)
    local direction = (to - from).Unit -- cylinder adornment height runs along local Y
    local reference = if math.abs(direction:Dot(Vector3.yAxis)) > 0.94
        then Vector3.xAxis else Vector3.yAxis
    local right = reference:Cross(direction).Unit
    local back = right:Cross(direction).Unit
    return CFrame.fromMatrix((from + to) * 0.5, right, direction, back)
end

function BranchPreview.new(workspace)
    local self = setmetatable({}, BranchPreview)
    self.workspace = workspace
    self.folder = nil
    self.parts = {}
    self.marker = nil
    return self
end

function BranchPreview:Clear()
    if self.folder then self.folder:Destroy() end
    self.folder = nil
    self.parts = {}
    self.marker = nil
end

function BranchPreview:Ensure()
    if self.folder then return true end
    local coreGui = game:GetService("CoreGui")
    local folder = Instance.new("Folder")
    folder.Name = "Game1LandscapePainterOverlay"
    folder.Parent = coreGui
    local marker = Instance.new("SphereHandleAdornment")
    marker.Name = "Cursor"
    marker.Adornee = self.workspace.Terrain
    marker.AlwaysOnTop = false
    marker.Transparency = 0.12
    marker.Parent = folder
    self.folder = folder
    self.marker = marker
    return true
end

function BranchPreview:Show(anchors, cursor, diameter, color)
    if not self:Ensure() then return end
    local terrainFrame = self.workspace.Terrain.CFrame
    self.marker.Radius = math.max(0.11, diameter * 0.5)
    self.marker.CFrame = terrainFrame:ToObjectSpace(CFrame.new(BranchGeometry.VisiblePoint(cursor, diameter)))
    self.marker.Color3 = color
    self.marker.Visible = true
    local required = if anchors then #anchors - 1 else 0
    for i = 1, required do
        local a = BranchGeometry.VisiblePoint(anchors[i], diameter)
        local b = BranchGeometry.VisiblePoint(anchors[i + 1], diameter)
        local length = (b - a).Magnitude
        local part = self.parts[i]
        if not part then
            part = Instance.new("CylinderHandleAdornment")
            part.Name = "Preview" .. tostring(i)
            part.Adornee = self.workspace.Terrain
            part.Transparency = 0.35
            part.AlwaysOnTop = false
            part.Parent = self.folder
            self.parts[i] = part
        end
        if length > 0.001 then
            part.Height = length
            part.Radius = diameter * 0.5
            part.CFrame = terrainFrame:ToObjectSpace(segmentFrame(a, b))
            part.Color3 = color
            part.Visible = true
        else
            part.Visible = false
        end
    end
    for i = required + 1, #self.parts do
        self.parts[i].Visible = false
    end
end

function BranchPreview:Hide()
    if self.marker then self.marker.Visible = false end
    for _, part in ipairs(self.parts) do part.Visible = false end
end

return BranchPreview

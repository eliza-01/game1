local HttpService = game:GetService("HttpService")
local BranchPath = require(script.Parent.BranchPath)
local BranchGeometry = require(script.Parent.BranchGeometry)
local BranchPreview = require(script.Parent.BranchPreview)

local BranchPlacement = {}
BranchPlacement.__index = BranchPlacement

local MAX_RAY_LENGTH = 2048
local MAX_SEGMENT_LENGTH = 250

function BranchPlacement.new(workspace, history, pluginMouse, setStatus)
    local self = setmetatable({}, BranchPlacement)
    self.workspace = workspace
    self.history = history
    self.mouse = pluginMouse
    self.setStatus = setStatus
    self.preview = BranchPreview.new(workspace)
    self.active = false
    self.anchor = nil
    self.cursor = nil
    self.strokeId = nil
    self.segmentNumber = 0
    self.lastMove = 0
    self.thickness = 0.24
    self.level = 0
    self.color = Color3.fromRGB(89, 123, 60)
    return self
end

function BranchPlacement:SetSettings(diameter, level, color)
    self.thickness = math.clamp(diameter, 0.04, 4)
    self.level = math.clamp(math.floor(level), 0, 4)
    self.color = color
    if self.active then self:UpdateCursor(true) end
end

function BranchPlacement:Start()
    self.active = true
    self.anchor = nil
    self.strokeId = HttpService:GenerateGUID(false)
    self.segmentNumber = 0
    self.lastMove = 0
    self.setStatus("Кликни первую точку на поверхности")
    self:UpdateCursor(true)
end

function BranchPlacement:Stop()
    self.active = false
    self.anchor = nil
    self.cursor = nil
    self.preview:Clear()
    self.setStatus("Готово · выбери «Ветка», чтобы начать снова")
end

function BranchPlacement:Raycast(origin: Vector3, direction: Vector3)
    local filter = {}
    local output = self.workspace:FindFirstChild("Game1LandscapeDecor")
    if output then table.insert(filter, output) end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = filter
    params.IgnoreWater = true
    return self.workspace:Raycast(origin, direction, params)
end

function BranchPlacement:ProjectToFacingSurface(point: Vector3, outwardNormal: Vector3, spanLength: number)
    -- Search *from the visible side* back into the surface. A reverse-facing
    -- triangle or an opposite wall face is not accepted as a valid snap.
    local reach = math.clamp(spanLength * 0.75, 1.5, 14)
    local result = self:Raycast(point + outwardNormal * reach, -outwardNormal * (reach * 2))
    if not result or result.Normal:Dot(outwardNormal) < 0.25 then
        return nil
    end
    if (result.Position - point).Magnitude > reach then
        return nil
    end
    return {position = result.Position, normal = result.Normal}
end

function BranchPlacement:PathTo(nextAnchor)
    if not self.anchor then return nil, nil end
    return BranchPath.Build(self.anchor, nextAnchor, self.level,
        function(point, normal, length)
            return self:ProjectToFacingSurface(point, normal, length)
        end)
end

function BranchPlacement:UpdateCursor(force)
    if not self.active then return end
    local now = os.clock()
    if not force and now - self.lastMove < 1 / 30 then return end
    self.lastMove = now
    local ray = self.mouse.UnitRay
    local hit = self:Raycast(ray.Origin, ray.Direction * MAX_RAY_LENGTH)
    if not hit then
        self.cursor = nil
        self.preview:Hide()
        return
    end
    local nextAnchor = {position = hit.Position, normal = hit.Normal}
    self.cursor = nextAnchor
    local anchors
    if self.anchor and (self.anchor.position - nextAnchor.position).Magnitude > 0.02 then
        anchors = self:PathTo(nextAnchor)
    end
    self.preview:Show(anchors, nextAnchor, self.thickness, self.color)
end

local function storeAnchor(model, prefix, anchor)
    model:SetAttribute(prefix .. "Point", anchor.position)
    model:SetAttribute(prefix .. "Normal", anchor.normal)
end

function BranchPlacement:Commit(toAnchor)
    local fromAnchor = self.anchor
    if not fromAnchor then return false end
    if (toAnchor.position - fromAnchor.position).Magnitude > MAX_SEGMENT_LENGTH then
        self.setStatus("Слишком длинный отрезок (максимум 250 studs)")
        return false
    end
    local anchors, stats = self:PathTo(toAnchor)
    if not anchors or #anchors < 2 or (toAnchor.position - fromAnchor.position).Magnitude < 0.05 then
        self.setStatus("Поставь следующую точку чуть дальше")
        return false
    end
    local record = self.history:TryBeginRecording("Game1LandscapeBranch", "Draw landscape branch")
    if not record then
        self.setStatus("Studio не разрешила запись Undo · ветка не создана")
        return false
    end
    local ok, err = pcall(function()
        local root = self.workspace:FindFirstChild("Game1LandscapeDecor")
        if root and not root:IsA("Folder") then
            error("Workspace.Game1LandscapeDecor must be a Folder")
        end
        if not root then
            root = Instance.new("Folder")
            root.Name = "Game1LandscapeDecor"
            root.Parent = self.workspace
        end
        local branches = root:FindFirstChild("Branches")
        if branches and not branches:IsA("Folder") then
            error("Game1LandscapeDecor.Branches must be a Folder")
        end
        if not branches then
            branches = Instance.new("Folder")
            branches.Name = "Branches"
            branches.Parent = root
        end
        local model = Instance.new("Model")
        model.Name = "Branch_" .. HttpService:GenerateGUID(false):sub(1, 8)
        model:SetAttribute("SchemaVersion", 1)
        model:SetAttribute("AuthoringTool", "Game1LandscapePainter")
        model:SetAttribute("StrokeId", self.strokeId)
        model:SetAttribute("SegmentIndex", self.segmentNumber + 1)
        model:SetAttribute("Thickness", self.thickness)
        model:SetAttribute("ColorHex", "#" .. self.color:ToHex())
        model:SetAttribute("SurfaceFollowLevel", self.level)
        model:SetAttribute("SnappedMidpoints", stats.snapped)
        model:SetAttribute("UnsnappedMidpoints", stats.missed)
        storeAnchor(model, "Start", fromAnchor)
        storeAnchor(model, "End", toAnchor)
        BranchGeometry.CreateSegments(model, anchors, self.thickness, self.color, false)
        if #model:GetChildren() == 0 then error("No visible geometry was generated") end
        model.Parent = branches
    end)
    if not ok then
        self.history:FinishRecording(record, Enum.FinishRecordingOperation.Cancel)
        self.setStatus("Ошибка размещения: " .. tostring(err))
        return false
    end
    self.history:FinishRecording(record, Enum.FinishRecordingOperation.Commit)
    self.segmentNumber += 1
    local note = if stats.missed > 0 then " · " .. stats.missed .. " точек без прилегания" else ""
    self.setStatus("Ветка размещена · продолжай или Enter для завершения" .. note)
    return true
end

function BranchPlacement:Click()
    if not self.active then return end
    -- Always refresh the hit on click; the cursor preview might have been
    -- throttled during fast movement.
    self:UpdateCursor(true)
    if not self.cursor then
        self.setStatus("Наведи курсор на поверхность")
        return
    end
    local selected = {position = self.cursor.position, normal = self.cursor.normal}
    if not self.anchor then
        self.anchor = selected
        self.setStatus("Первая точка поставлена · выбери следующую")
        return
    end
    if self:Commit(selected) then
        self.anchor = selected -- continuous polyline until Enter
    end
end

return BranchPlacement

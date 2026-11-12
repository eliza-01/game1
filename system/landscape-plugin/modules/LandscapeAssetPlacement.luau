-- Edit-mode pivot placement with a surface reticle, reversible history,
-- optional procedural tether, and a detached published-model template.
local HttpService = game:GetService("HttpService")
local Surface = require(script.Parent.LandscapeSurface)
local StemTarget = require(script.Parent.LandscapeStemTarget)
local BranchGeometry = require(script.Parent.BranchGeometry)
local BranchPreview = require(script.Parent.BranchPreview)
local Profiles = require(script.Parent.LandscapeProfiles)
local SwayAuthoring = require(script.Parent.LandscapeSwayAuthoring)
local DecoTransform = require(script.Parent.DecoTransform)

local Placement = {}
Placement.__index = Placement
local RAY_LENGTH = 2048
local MAX_PREVIEW_HZ = 30
local ROOT_NAME = "Game1LandscapeDecor"
local ASSETS_NAME = "Assets"
local LINE_NAME = "LandscapeAttachmentLine"
local STEM_LINK_NAME = "LandscapeAnchorStem"
local STEM_ATTACHMENTS_NAME = "Attachments"

local function makeTether(model: Model, hitPoint: Vector3, targetPoint: Vector3, settings)
    if not settings.tetherEnabled then return end
    if (targetPoint - hitPoint).Magnitude < 0.01 then error("подвес слишком короткий") end
    local line = Instance.new("Part")
    BranchGeometry.Apply(line, hitPoint, targetPoint,
        settings.thickness, Color3.fromHex(settings.color), false)
    line.Name = LINE_NAME
    line:SetAttribute("Game1LandscapeAttachment", true)
    line.Parent = model
end

local function replaceTether(model: Model, point: Vector3, target: Vector3, settings)
    local old = model:FindFirstChild(LINE_NAME)
    if old and (not old:IsA("Part") or old:GetAttribute("Game1LandscapeAttachment") ~= true) then
        error("LandscapeAttachmentLine занято сторонним объектом")
    end
    -- Generate a detached new line before modifying the existing assembly.
    local line = nil
    if settings.tetherEnabled then
        local container = Instance.new("Model")
        local ok, reason = pcall(makeTether, container, point, target, settings)
        if not ok then container:Destroy(); error(reason) end
        line = container:FindFirstChild(LINE_NAME)
        if line then line.Parent = nil end
        container:Destroy()
    end
    if old then old:Destroy() end
    if line then line.Parent = model end
end

local function authoredFolder(workspace)
    local root = workspace:FindFirstChild(ROOT_NAME)
    if root and not root:IsA("Folder") then error(ROOT_NAME .. " must be a Folder") end
    if not root then
        root = Instance.new("Folder")
        root.Name = ROOT_NAME
        root.Parent = workspace
    end
    local folder = root:FindFirstChild(ASSETS_NAME)
    if folder and not folder:IsA("Folder") then error(ROOT_NAME .. ".Assets must be a Folder") end
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = ASSETS_NAME
        folder.Parent = root
    end
    return folder
end

function Placement.new(workspace, history, mouse, selection, catalog, profiles, status)
    local self = setmetatable({}, Placement)
    self.workspace = workspace
    self.history = history
    self.mouse = mouse
    self.selection = selection
    self.catalog = catalog
    self.profiles = profiles
    self.status = status
    self.preview = BranchPreview.new(workspace)
    self.config = Profiles.Validate({yaw = 0, pitch = 0, roll = 0,
        tetherEnabled = false, swayEnabled = false,
        length = 2, thickness = 0.02, color = "#343B38"})
    self.template = nil
    self.ghost = nil
    self.row = nil
    self.authoredPivotRotation = nil
    self.authoredSupportOffset = nil
    self.cursor = nil
    self.active = false
    self.lastMove = 0
    self.pendingConfigPreview = false
    self.targetMode = "auto" -- auto | surface | stem
    self.stemParts = {}
    self.stemFolder = nil
    self.lastStemScan = 0
    self.lastTargetKind = nil
    self.lastPreviewError = nil
    return self
end

function Placement:SetConfiguration(config)
    self.config = Profiles.Validate(config)
    if not self.active then return end
    -- Slider drags can fire many times per second. Preserve fluid preview
    -- without rebuilding a large published mesh more than 30 times/second.
    if os.clock() - self.lastMove >= 1 / MAX_PREVIEW_HZ then
        self:UpdateCursor(false)
    elseif not self.pendingConfigPreview then
        self.pendingConfigPreview = true
        task.delay(1 / MAX_PREVIEW_HZ, function()
            self.pendingConfigPreview = false
            if self.active then self:UpdateCursor(true) end
        end)
    end
end

function Placement:Effective()
    local _, activeId = self.profiles:List()
    local active = if activeId then self.profiles:Find(activeId) else nil
    return active or self.config
end

function Placement:SelectAsset(row)
    -- A failed LoadAssetAsync must not discard the previously selected asset.
    local model = self.catalog:Load(row)
    -- Cache the canonical imported pose before anything is previewed or
    -- augmented with a tether. It is the same geometry-frame calculation as
    -- DecoManager, not a new pivot chosen from the model's bounding box.
    local ok, rotation, support = pcall(function()
        return DecoTransform.authoredPivotRotation(model),
            DecoTransform.supportOffset(model)
    end)
    if not ok then model:Destroy(); error("Не удалось прочитать pivot ассета: " .. tostring(rotation)) end
    local previous = self.template
    self:HideGhost()
    self.template = model
    self.row = row
    self.authoredPivotRotation = rotation
    self.authoredSupportOffset = support
    if previous then previous:Destroy() end
    self.status("Выбран " .. row.slug .. " · наведи прицел на стебель или поверхность")
    self:UpdateCursor(true)
end

function Placement:SetTargetMode(mode)
    if mode ~= "auto" and mode ~= "surface" and mode ~= "stem" then
        error("Неизвестный режим прицела")
    end
    self.targetMode = mode
    self.lastTargetKind = nil
    if self.active then self:UpdateCursor(true) end
end

function Placement:ScanStems(force)
    if force or os.clock() - self.lastStemScan > 0.5 then
        self.stemParts, self.stemFolder = StemTarget.Collect(self.workspace)
        self.lastStemScan = os.clock()
    end
end

function Placement:ResolveHit()
    local surface = Surface.Raycast(self.workspace, self.mouse, RAY_LENGTH)
    -- Roblox RaycastResult has Position/Normal but no kind/stem/branch fields.
    -- Convert it to the same target record returned by StemTarget.Find before
    -- UpdateCursor reads those fields. Keep the raw hit for stem occlusion.
    local surfaceTarget = if surface then {
        Position = surface.Position,
        Normal = surface.Normal,
        kind = "surface",
    } else nil
    if self.targetMode == "surface" then return surfaceTarget end
    self:ScanStems(false)
    local stem = StemTarget.Find(self.stemParts, self.stemFolder,
        self.mouse.UnitRay, surface, RAY_LENGTH)
    if stem then return stem end
    if self.targetMode == "stem" then return nil end
    return surfaceTarget
end

function Placement:Start(): boolean
    if not self.row or not self.template then
        self.status("Сначала выбери опубликованный ассет в каталоге")
        return false
    end
    self.active = true
    self.lastMove = 0
    self:ScanStems(true)
    self.status("Прицел активен · ЛКМ размещает на поверхности или стебле · Enter завершает")
    self:UpdateCursor(true)
    return true
end

function Placement:HideGhost()
    if self.ghost then self.ghost:Destroy(); self.ghost = nil end
    self.preview:Clear()
end

function Placement:Stop()
    self.active = false
    self.cursor = nil
    self.lastTargetKind = nil
    self.lastPreviewError = nil
    self:HideGhost()
end

function Placement:EnsureGhost()
    if self.ghost and self.ghost.Parent ~= nil and self.ghost.Parent ~= self.workspace.CurrentCamera then
        self.ghost:Destroy()
        self.ghost = nil
    end
    if self.ghost then return self.ghost end
    if not self.template or not self.workspace.CurrentCamera then return nil end
    local clone = self.template:Clone()
    if not clone then error("Невозможно скопировать опубликованный ассет для предпросмотра") end
    clone.Name = "__Game1LandscapePreview"
    for _, obj in ipairs(clone:GetDescendants()) do
        if obj:IsA("BasePart") then
            obj.Anchored = true
            obj.CanCollide = false
            obj.CanTouch = false
            obj.CanQuery = false
            obj.CastShadow = false
            obj.Transparency = math.max(obj.Transparency, 0.5)
        end
    end
    clone.Archivable = false
    clone.Parent = self.workspace.CurrentCamera
    self.ghost = clone
    return clone
end

function Placement:UpdateCursor(force)
    if not self.active then return end
    local now = os.clock()
    if not force and now - self.lastMove < 1 / MAX_PREVIEW_HZ then return end
    self.lastMove = now
    local hit = self:ResolveHit()
    if not hit then
        self.cursor = nil
        self.preview:Hide()
        if self.ghost then self.ghost.Parent = nil end
        if self.lastTargetKind ~= "none" then
            self.lastTargetKind = "none"
            self.status(if self.targetMode == "stem" then
                "Нет стебля под прицелом · выбери Авто или Поверхность для земли/стен"
                else "Прицел не видит поверхность · наведи на Terrain или доступный для Raycast Part")
        end
        return
    end
    self.cursor = {point = hit.Position, normal = hit.Normal,
        kind = hit.kind or "surface", stem = hit.stem, branch = hit.branch}
    if self.lastTargetKind ~= self.cursor.kind then
        self.lastTargetKind = self.cursor.kind
        if self.cursor.kind == "stem" then
            self.status("Цель: стебель · точка крепления выбрана · ЛКМ размещает")
        else
            self.status("Цель: поверхность · геометрия касается поверхности, исходный Pivot сохранён · ЛКМ размещает")
        end
    end
    local config = self:Effective()
    local camera = self.workspace.CurrentCamera
    local cameraLook = if camera then camera.CFrame.LookVector else Vector3.new(0, 0, -1)
    local pivot = Surface.Pivot(hit.Position, hit.Normal, config,
        self.authoredPivotRotation, self.authoredSupportOffset, cameraLook,
        self.cursor.kind)
    -- Share the same calculated frame for preview, click placement and rope.
    self.cursor.pivot = pivot
    self.cursor.facingDirection = cameraLook
    -- A failure to draw the temporary ghost/adornment must not invalidate
    -- the computed hit or disable click-to-place. Keep the two views isolated.
    local ghostOK, ghostError = pcall(function()
        local ghost = self:EnsureGhost()
        if ghost then
            if ghost.Parent == nil then ghost.Parent = self.workspace.CurrentCamera end
            ghost:PivotTo(pivot)
        end
    end)
    local markerOK, markerError = pcall(function()
        local anchors = nil
        if config.tetherEnabled then
            anchors = {
                {position = hit.Position, normal = hit.Normal},
                {position = pivot.Position, normal = Vector3.zero},
            }
        end
        self.preview:Show(anchors, {position = hit.Position, normal = hit.Normal},
            if config.tetherEnabled then config.thickness else 0.2,
            if config.tetherEnabled then Color3.fromHex(config.color) else Color3.fromRGB(65, 207, 169))
    end)
    if not ghostOK or not markerOK then
        local message = if not ghostOK then tostring(ghostError) else tostring(markerError)
        if self.lastPreviewError ~= message then
            self.lastPreviewError = message
            self.status("Ошибка отображения прицела: " .. message .. " · размещение ЛКМ доступно")
            warn("[Game1LandscapePainter] preview: " .. message)
        end
    else
        self.lastPreviewError = nil
    end
end

local function writeMetadata(model, cursor, row, config, authoredRotation, supportOffset)
    model:SetAttribute("LandscapeSchemaVersion", 3)
    model:SetAttribute("LandscapeAuthoredPivotRotation", authoredRotation)
    model:SetAttribute("LandscapeAuthoredSupportOffset", supportOffset)
    model:SetAttribute("LandscapeFacingDirection", cursor.facingDirection)
    model:SetAttribute("LandscapeAuthoringTool", "Game1LandscapePainter")
    model:SetAttribute("LandscapeAssetSlug", row.slug)
    model:SetAttribute("LandscapeModelAssetId", tostring(row.model_asset_id))
    model:SetAttribute("LandscapeSurfacePoint", cursor.point)
    model:SetAttribute("LandscapeSurfaceNormal", cursor.normal)
    model:SetAttribute("LandscapeYaw", config.yaw)
    model:SetAttribute("LandscapePitch", config.pitch)
    model:SetAttribute("LandscapeRoll", config.roll)
    model:SetAttribute("LandscapeTetherEnabled", config.tetherEnabled)
    model:SetAttribute("LandscapeSwayEnabled", config.swayEnabled)
    model:SetAttribute("LandscapeTetherLength", config.length)
    model:SetAttribute("LandscapeTetherThickness", config.thickness)
    model:SetAttribute("LandscapeTetherColor", config.color)
    model:SetAttribute("LandscapeAnchorKind", cursor.kind or "surface")
end

local function attachToStem(instance: Model, cursor)
    local stem = cursor.stem
    local branch = cursor.branch
    if not stem or not branch or not stem:IsDescendantOf(branch)
        or branch:GetAttribute("AuthoringTool") ~= "Game1LandscapePainter" then
        error("Стебель больше не существует · наведи прицел повторно")
    end
    local link = Instance.new("ObjectValue")
    link.Name = STEM_LINK_NAME
    link.Value = stem
    link.Parent = instance
    instance:SetAttribute("LandscapeStemLocalPoint", stem.CFrame:PointToObjectSpace(cursor.point))
    instance:SetAttribute("LandscapeStemLocalNormal", stem.CFrame:VectorToObjectSpace(cursor.normal))
    instance:SetAttribute("LandscapeBranchStrokeId", branch:GetAttribute("StrokeId"))
    local attachments = branch:FindFirstChild(STEM_ATTACHMENTS_NAME)
    if attachments and not attachments:IsA("Folder") then
        error("У стебля занято имя Attachments")
    end
    if not attachments then
        attachments = Instance.new("Folder")
        attachments.Name = STEM_ATTACHMENTS_NAME
        attachments.Parent = branch
    end
    return attachments
end

function Placement:Click()
    if not self.active then return end
    self:UpdateCursor(true)
    local cursor = self.cursor
    if not cursor then
        self.status(if self.targetMode == "stem" then "Прицел не видит стебель"
            else "Прицел не видит точку размещения")
        return
    end
    local row, template = self.row, self.template
    if not row or not template then return end
    local config = self:Effective()
    local record = self.history:TryBeginRecording("Game1LandscapeAsset", "Place landscape asset")
    if not record then self.status("Studio не разрешила создать Undo-запись"); return end
    local instance = nil
    local ok, reason = pcall(function()
        local folder = authoredFolder(self.workspace)
        instance = template:Clone()
        instance.Name = row.slug .. "_" .. HttpService:GenerateGUID(false):sub(1, 8)
        local pivot = cursor.pivot
        if typeof(pivot) ~= "CFrame" then error("Предпросмотр не определил pivot размещения") end
        instance:PivotTo(pivot)
        makeTether(instance, cursor.point, pivot.Position, config)
        SwayAuthoring.Sync(instance, config)
        writeMetadata(instance, cursor, row, config,
            self.authoredPivotRotation, self.authoredSupportOffset)
        if cursor.kind == "stem" then
            instance.Parent = attachToStem(instance, cursor)
        else
            instance.Parent = folder
        end
    end)
    if not ok then
        if instance then instance:Destroy() end
        self.history:FinishRecording(record, Enum.FinishRecordingOperation.Cancel)
        self.status("Размещение отменено: " .. tostring(reason))
        return
    end
    self.history:FinishRecording(record, Enum.FinishRecordingOperation.Commit)
    local targetNote = if cursor.kind == "stem" then " · прикреплено к стеблю"
        else " · на поверхности"
    local physicsNote = if config.swayEnabled then " · событийное покачивание (Play)" else " · Anchored"
    self.status("Размещено: " .. row.slug .. targetNote .. physicsNote ..
        " · следующий клик ставит ещё один")
end

local function selectedModel(selection)
    local chosen = selection:Get()
    if #chosen ~= 1 then error("Выдели одну Model в Explorer или во viewport") end
    local current = chosen[1]
    if current:IsA("Model") then return current end
    while current and current ~= game do
        if current:IsA("Model") and current:GetAttribute("LandscapeAuthoringTool") == "Game1LandscapePainter" then
            return current
        end
        current = current.Parent
    end
    error("Нужна Model; для выбора дочернего MeshPart выдели корневую модель")
end

function Placement:ApplyToSelection(config)
    config = Profiles.Validate(config)
    local model = selectedModel(self.selection)
    if not model:IsDescendantOf(self.workspace) then
        error("Apply работает только с Model в Workspace")
    end
    local point = model:GetAttribute("LandscapeSurfacePoint")
    local normal = model:GetAttribute("LandscapeSurfaceNormal")
    local managed = model:GetAttribute("LandscapeAuthoringTool") == "Game1LandscapePainter"
        and typeof(point) == "Vector3" and typeof(normal) == "Vector3"
        and normal.Magnitude > 0.0001
    -- A managed stem anchor travels with its parent Branch model. Rebuild
    -- the world-space point from the referenced segment before Apply, not
    -- from stale position Attributes saved before a Studio move operation.
    local anchoredStem = model:GetAttribute("LandscapeAnchorKind") == "stem"
    if anchoredStem then
        local link = model:FindFirstChild(STEM_LINK_NAME)
        local localPoint = model:GetAttribute("LandscapeStemLocalPoint")
        local localNormal = model:GetAttribute("LandscapeStemLocalNormal")
        if not managed or not link or not link:IsA("ObjectValue")
            or not link.Value or not link.Value:IsA("Part")
            or typeof(localPoint) ~= "Vector3" or typeof(localNormal) ~= "Vector3"
            or localNormal.Magnitude < 0.0001 then
            error("Крепление к стеблю повреждено · Apply отменён")
        end
        local stems = self.workspace:FindFirstChild(ROOT_NAME)
        stems = if stems then stems:FindFirstChild("Branches") else nil
        local branch = StemTarget.IsAuthoredStem(link.Value, stems)
        if not branch or not model:IsDescendantOf(branch) then
            error("Исходный стебель недоступен · Apply отменён")
        end
        point = link.Value.CFrame:PointToWorldSpace(localPoint)
        normal = link.Value.CFrame:VectorToWorldSpace(localNormal).Unit
    end
    if not managed and config.tetherEnabled then
        error("Для подвеса нужна точка крепления: сначала размести ассет прицелом")
    end
    local authoredRotation = model:GetAttribute("LandscapeAuthoredPivotRotation")
    local supportOffset = model:GetAttribute("LandscapeAuthoredSupportOffset")
    local facingDirection = model:GetAttribute("LandscapeFacingDirection")
    if managed and (typeof(authoredRotation) ~= "CFrame"
        or typeof(supportOffset) ~= "number"
        or typeof(facingDirection) ~= "Vector3") then
        -- A pre-M295 model has no saved FBX basis. Its current world
        -- rotation is NOT its original rig rotation. Only the matching
        -- published template can repair it reliably.
        if not self.row or not self.template
            or tostring(self.row.model_asset_id) ~= tostring(model:GetAttribute("LandscapeModelAssetId"))
            or self.authoredPivotRotation == nil or self.authoredSupportOffset == nil then
            error("Старое размещение: выбери в каталоге тот же опубликованный ассет, затем Apply для исправления pivot")
        end
        authoredRotation = self.authoredPivotRotation
        supportOffset = self.authoredSupportOffset
        local camera = self.workspace.CurrentCamera
        facingDirection = if camera then camera.CFrame.LookVector else Vector3.new(0, 0, -1)
    end
    local record = self.history:TryBeginRecording("Game1LandscapeApplyProfile", "Apply landscape profile")
    if not record then error("Studio не разрешила Undo-запись") end
    local previousPivot = model:GetPivot()
    local previousPoint = model:GetAttribute("LandscapeSurfacePoint")
    local oldConfig = {
        yaw = model:GetAttribute("LandscapeYaw") or 0,
        pitch = model:GetAttribute("LandscapePitch") or 0,
        roll = model:GetAttribute("LandscapeRoll") or 0,
        tetherEnabled = model:GetAttribute("LandscapeTetherEnabled") == true,
        swayEnabled = model:GetAttribute("LandscapeSwayEnabled") == true,
        length = model:GetAttribute("LandscapeTetherLength") or 2,
        thickness = model:GetAttribute("LandscapeTetherThickness") or 0.02,
        color = model:GetAttribute("LandscapeTetherColor") or "#343B38",
    }
    local oldLine = model:FindFirstChild(LINE_NAME)
    local savedLine = if oldLine then oldLine:Clone() else nil
    local previousAttributes = {}
    local attributeKeys = {"LandscapeYaw", "LandscapePitch", "LandscapeRoll",
        "LandscapeTetherEnabled", "LandscapeSwayEnabled", "LandscapeTetherLength",
        "LandscapeTetherThickness", "LandscapeTetherColor",
        "LandscapeSurfacePoint", "LandscapeSurfaceNormal", "LandscapeSchemaVersion",
        "LandscapeAuthoredPivotRotation", "LandscapeAuthoredSupportOffset",
        "LandscapeFacingDirection"}
    for _, key in ipairs(attributeKeys) do
        previousAttributes[key] = model:GetAttribute(key)
    end
    local ok, reason = pcall(function()
        local targetKind = if anchoredStem then "stem" else "surface"
        local pivot = if managed then Surface.Pivot(point, normal, config,
            authoredRotation, supportOffset, facingDirection, targetKind) else
            CFrame.new(previousPivot.Position) * CFrame.Angles(
                math.rad(config.pitch), math.rad(config.yaw), math.rad(config.roll))
        model:PivotTo(pivot)
        if managed then
            replaceTether(model, point, pivot.Position, config)
            SwayAuthoring.Sync(model, config)
            -- For regular surface placement the point is unchanged; for a
            -- moved branch this refreshes the authored world-space cache.
            model:SetAttribute("LandscapeSurfacePoint", point)
            model:SetAttribute("LandscapeSurfaceNormal", normal)
            -- Do not overwrite the registered Model ID.
            model:SetAttribute("LandscapeYaw", config.yaw)
            model:SetAttribute("LandscapePitch", config.pitch)
            model:SetAttribute("LandscapeRoll", config.roll)
            model:SetAttribute("LandscapeTetherEnabled", config.tetherEnabled)
            model:SetAttribute("LandscapeSwayEnabled", config.swayEnabled)
            model:SetAttribute("LandscapeTetherLength", config.length)
            model:SetAttribute("LandscapeTetherThickness", config.thickness)
            model:SetAttribute("LandscapeTetherColor", config.color)
            model:SetAttribute("LandscapeSchemaVersion", 3)
            model:SetAttribute("LandscapeAuthoredPivotRotation", authoredRotation)
            model:SetAttribute("LandscapeAuthoredSupportOffset", supportOffset)
            model:SetAttribute("LandscapeFacingDirection", facingDirection)
        end
    end)
    if not ok then
        pcall(function()
            -- Restore the static authoring state; Undo.Cancel restores the
            -- complete prior model if the editor transaction fails.
            SwayAuthoring.Sync(model, oldConfig)
            model:PivotTo(previousPivot)
            local existing = model:FindFirstChild(LINE_NAME)
            if existing and existing:GetAttribute("Game1LandscapeAttachment") == true then existing:Destroy() end
            if savedLine then savedLine.Parent = model; savedLine = nil end
            for _, key in ipairs(attributeKeys) do
                model:SetAttribute(key, previousAttributes[key])
            end
        end)
        if savedLine then savedLine:Destroy() end
        self.history:FinishRecording(record, Enum.FinishRecordingOperation.Cancel)
        error(reason)
    end
    if savedLine then savedLine:Destroy() end
    self.history:FinishRecording(record, Enum.FinishRecordingOperation.Commit)
    if managed then
        local physicsNote = if config.swayEnabled then " · покачивание по событиям" else " · Anchored"
        self.status("Профиль применён к " .. model.Name .. " · крепление сохранено" .. physicsNote)
    else
        self.status("Поворот применён к " .. model.Name .. " · без подвеса (нет surface anchor)")
    end
end

function Placement:Destroy()
    self:Stop()
    if self.template then self.template:Destroy(); self.template = nil end
end

return Placement

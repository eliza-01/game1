-- M343B1: multi-selection Collision Capture. No authoring folders or pivot edits.
-- One published Location Model + arbitrary selected primitive Parts (any ancestry).
-- Selected instances are NEVER reparented, renamed, moved or changed.
local Carrier = require(script.Parent.StudioLocationRigCarrier)
local MeshPhysics = require(script.Parent.StudioMeshPhysicsCore)
local History = require(script.Parent.StudioPublishedMeshHistory)
local PREVIEW_LOCATION = "__Game1LocationCollisionPreview"
local PREVIEW_HOUSE = "__Game1HouseCollisionPreview"
local function isHouse(command: any): boolean
    return command.command == "house-collision-authoring-v1"
end
local function previewName(command: any): string
    return if isHouse(command) then PREVIEW_HOUSE else PREVIEW_LOCATION
end
local MAX_PARTS = 256

local function partsToCFrame(part: BasePart, rootPivot: CFrame): {number}
    return {rootPivot:ToObjectSpace(part.CFrame):GetComponents()}
end

local function shapeOf(part: Instance): string
    if part:IsA("Part") then
        -- Studio now creates wedges as Part.Shape, not only as WedgePart.
        -- Normalize both representations to the existing Blueprint shape IDs.
        local shape = part.Shape
        if shape == Enum.PartType.Block then return "Block" end
        if shape == Enum.PartType.Ball then return "Ball" end
        if shape == Enum.PartType.Cylinder then return "Cylinder" end
        if shape == Enum.PartType.Wedge then return "Wedge" end
        if shape == Enum.PartType.CornerWedge then return "CornerWedge" end
        error("Unsupported collision Part.Shape: " .. tostring(shape) .. " (" .. part:GetFullName() .. ")")
    end
    if part:IsA("WedgePart") then return "Wedge" end
    if part:IsA("CornerWedgePart") then return "CornerWedge" end
    error("Select only Part, WedgePart or CornerWedgePart; MeshPart is not a collision primitive")
end

local function sameInventory(root: Model, version: any): boolean
    if type(version) ~= "table" or type(version.meshes) ~= "table"
        or #version.meshes < 1 then return false end
    local expected = {}
    for _, item in ipairs(version.meshes) do
        if type(item.meshId) ~= "string" or not item.meshId:match("^[1-9]%d*$")
            or type(item.count) ~= "number" or item.count < 1
            or item.count > 4096 or expected[item.meshId] then return false end
        expected[item.meshId] = item.count
    end
    local actual = {}
    local total = 0
    for _, part in ipairs(root:GetDescendants()) do
        if part:IsA("MeshPart") and not Carrier.IsCarrier(part)
            and not MeshPhysics.IsCollider(part.Name)
            and part:GetAttribute("Game1DecoPhysicsOnly") ~= true then
            local id = History.Id(part.MeshId)
            if id == "" or expected[id] == nil then return false end
            actual[id] = (actual[id] or 0) + 1
            total += 1
        end
    end
    if total == 0 then return false end
    for id, count in pairs(expected) do
        if actual[id] ~= count then return false end
    end
    return true
end

-- Only members returned by Studio Selection:Get() count as authoring inputs.
-- Generated Parts may appear in a mixed Studio selection, but must NEVER
-- become Blueprint recipes. Ignore them; don't mutate Studio's selection.
local function selectedModel(selection: any, workspaceRef: Workspace, command: any, needParts: boolean): (Model, {BasePart}, number)
    local picked = selection:Get()
    local root: Model? = nil
    local parts: {BasePart} = {}
    local ignoredGenerated = 0
    local observed = {}
    for _, item in ipairs(picked) do
        if #observed < 8 then
            table.insert(observed, item.ClassName .. " " .. item:GetFullName())
        end
        if item:IsA("Model") then
            if root then error("Select exactly ONE published Model plus original Parts") end
            root = item
        elseif item:IsA("BasePart") and (
            item:GetAttribute("Game1LocationCollisionOwned") == true
            or item:GetAttribute("Game1HouseCollisionOwned") == true
            or item.Name:sub(1, 17) == "__Game1Collision_") then
            ignoredGenerated += 1
        else
            -- Reject all unsupported classes, including visual MeshParts.
            shapeOf(item)
            if not item:IsA("BasePart") then error("Selected collision must be a BasePart") end
            table.insert(parts, item)
        end
    end
    local selectionReport = string.format(
        "Studio Selection:Get() returned %d objects; generated ignored: %d; actual: %s",
        #picked, ignoredGenerated, table.concat(observed, " | "))
    if root == nil or not root:IsDescendantOf(workspaceRef) then
        error("Select one published Model in Workspace. " .. selectionReport)
    end
    local camera = workspaceRef.CurrentCamera
    if camera and root:IsDescendantOf(camera) then error("Cannot author collision on Camera Model") end
    for _, item in ipairs(parts) do
        if not item:IsDescendantOf(workspaceRef) or (camera and item:IsDescendantOf(camera))
            then
            error("Collision Parts must be in Workspace, not in Camera")
        end
        local preview = workspaceRef:FindFirstChild(previewName(command))
        if preview and item:IsDescendantOf(preview) then
            error("Do not Capture generated Collision Preview Parts")
        end
    end
    if needParts and (#parts < 1 or #parts > MAX_PARTS) then
        error((if isHouse(command) then "Select the House Model together with 1..256 ORIGINAL collision Parts. "
            else "Select the Location Model together with 1..256 ORIGINAL collision Parts. ")
            .. selectionReport)
    end
    -- House identity is a managed, published plot preview. No guessing by name
    -- or by coincidentally matching Mesh IDs. Location retains its ID inventory.
    if isHouse(command) then
        if root.Name ~= command.slug or root:GetAttribute("Game1RealEstateSlug") ~= command.slug
            or root:GetAttribute("Game1PlotHousePreview") ~= true
            or tostring(root:GetAttribute("Game1HouseModelAssetId") or "") ~= command.expectedHouseModelId then
            error("Select the latest placed and synced " .. command.slug .. " House Model in a Plot")
        end
        if type(command.expectedHouseModelId) ~= "string"
            or not command.expectedHouseModelId:match("^[1-9]%d*$") then
            error("Published house rig identity missing")
        end
    else
        local cursor: Instance? = root
        while cursor and cursor ~= workspaceRef do
            local owned = cursor:GetAttribute("Game1DecoAssetSlug")
            if owned ~= nil and owned ~= command.slug then
                error("Selected Model belongs to another registered Location Asset")
            end
            if cursor:GetAttribute("Game1RealEstateSlug") ~= nil then
                error("Selected Model belongs to Real Estate, not Location Assets")
            end
            cursor = cursor.Parent
        end
        local versions = command.expectedVersions
        if type(versions) ~= "table" or #versions < 1 then
            error("Published Mesh ID inventory missing; refresh Location Asset history")
        end
        local verified = false
        for _, version in ipairs(versions) do
            if sameInventory(root, version) then verified = true break end
        end
        if not verified then
            error("Selected Model does not match published visual Mesh IDs of " .. command.slug ..
                ". Select the registered asset instance, not an unrelated Model")
        end
    end
    if math.abs(root:GetScale() - 1) > 0.0001 then
        error("Capture requires an unscaled Model (Scale=1). Original pivot preserved")
    end
    return root, parts, ignoredGenerated
end

local function acceptableId(value: any): boolean
    return type(value) == "string" and #value >= 1 and #value <= 64
        and value:match("^[A-Za-z0-9][A-Za-z0-9_%-]*$") ~= nil
end


-- A published visual MeshPart is a stable geometric anchor. Historic Models may
-- have PrimaryPart/PivotOffset while newly imported Models use WorldPivot.
-- Selecting an anchor by the CURRENT published Mesh ID (not by an editable name)
-- makes the Blueprint portable across both representations without changing pivots.
local function selectVisualAnchor(root: Model, command: any): (MeshPart, string)
    local versions = command.expectedVersions
    local current = if type(versions) == "table" then versions[1] else nil
    if type(current) ~= "table" or type(current.meshes) ~= "table" then
        error("Current published Mesh ID inventory unavailable for Collision Capture")
    end
    local allowed = {}
    for _, entry in ipairs(current.meshes) do
        if entry.count == 1 then allowed[entry.meshId] = true end
    end
    local candidates = {}
    for _, child in ipairs(root:GetDescendants()) do
        if child:IsA("MeshPart") and not Carrier.IsCarrier(child)
            and not MeshPhysics.IsCollider(child.Name)
            and child:GetAttribute("Game1DecoPhysicsOnly") ~= true then
            local mid = History.Id(child.MeshId)
            if allowed[mid] then
                candidates[mid] = candidates[mid] or {}
                table.insert(candidates[mid], child)
            end
        end
    end
    local ids = {}
    for mid, matches in pairs(candidates) do
        if #matches == 1 then table.insert(ids, mid) end
    end
    table.sort(ids)
    if #ids == 0 then
        error("No unique visual Mesh ID shared with the CURRENT publication. Place a fresh published instance before Capture")
    end
    return candidates[ids[1]][1], ids[1]
end

local function capture(root: Model, parts: {BasePart}, command: any): any
    -- IDs are optional: a unique simple name is used where available; repeated,
    -- Unicode or otherwise arbitrary names receive deterministic generated IDs.
    table.sort(parts, function(a, b)
        local aa, bb = a:GetFullName(), b:GetFullName()
        if aa ~= bb then return aa < bb end
        if a.Position.X ~= b.Position.X then return a.Position.X < b.Position.X end
        if a.Position.Y ~= b.Position.Y then return a.Position.Y < b.Position.Y end
        if a.Position.Z ~= b.Position.Z then return a.Position.Z < b.Position.Z end
        if a.Size.X ~= b.Size.X then return a.Size.X < b.Size.X end
        if a.Size.Y ~= b.Size.Y then return a.Size.Y < b.Size.Y end
        if a.Size.Z ~= b.Size.Z then return a.Size.Z < b.Size.Z end
        if a.Orientation.X ~= b.Orientation.X then return a.Orientation.X < b.Orientation.X end
        if a.Orientation.Y ~= b.Orientation.Y then return a.Orientation.Y < b.Orientation.Y end
        if a.Orientation.Z ~= b.Orientation.Z then return a.Orientation.Z < b.Orientation.Z end
        return a.ClassName < b.ClassName
    end)
    local proposed, frequencies, reserved = {}, {}, {}
    for _, part in ipairs(parts) do
        local explicit = part:GetAttribute("Game1CollisionPartId")
        local id = if acceptableId(explicit) then explicit else part.Name
        if not acceptableId(id) then id = nil end
        table.insert(proposed, id)
        if id then frequencies[id] = (frequencies[id] or 0) + 1 end
    end
    for _, id in ipairs(proposed) do
        if id and frequencies[id] == 1 then reserved[id] = true end
    end
    local used = {}
    local nextAuto = 0
    local recipes = {}
    local pivot = root:GetPivot() -- Read only; never edit the placed Model.
    local anchorPart, meshId, anchorFrame, anchorSize
    if not isHouse(command) then
        anchorPart, meshId = selectVisualAnchor(root, command)
        anchorFrame = pivot:ToObjectSpace(anchorPart.CFrame)
        anchorSize = anchorPart.Size
    end
    for index, part in ipairs(parts) do
        local id = proposed[index]
        if id == nil or frequencies[id] ~= 1 then
            repeat
                nextAuto += 1
                id = string.format("part_%04d", nextAuto)
            until not reserved[id] and not used[id]
        end
        used[id] = true
        local name = part.Name:gsub("[%c]", "_")
        if #name < 1 or #name > 96 or not utf8.len(name) then
            name = "CollisionPart"
        end
        local size = part.Size
        table.insert(recipes, {
            id = id, name = name, shape = shapeOf(part),
            size = {size.X, size.Y, size.Z},
            localCFrame = partsToCFrame(part, pivot),
            collisionGroup = part.CollisionGroup,
            canQuery = part.CanQuery,
            canTouch = part.CanTouch,
        })
    end
    if isHouse(command) then
        return {schemaVersion = 3, pivot = "Model:GetPivot()", parts = recipes}
    end
    return {schemaVersion = 2, pivot = "Model:GetPivot()",
        anchor = {meshId = meshId,
            localCFrame = {anchorFrame:GetComponents()},
            size = {anchorSize.X, anchorSize.Y, anchorSize.Z}},
        parts = recipes}
end

local function clearPreview(workspaceRef: Workspace, name: string): number
    local previous = workspaceRef:FindFirstChild(name)
    if not previous then return 0 end
    if not previous:IsA("Folder") or previous:GetAttribute("Game1CollisionPreviewOwned") ~= true then
        error("Reserved preview name is occupied by an unmanaged object; refusing to delete it")
    end
    local count = #previous:GetChildren()
    previous:Destroy()
    return count
end

local function preview(root: Model, blueprint: any, workspaceRef: Workspace, slug: string, name: string): number
    if type(blueprint) ~= "table" or (blueprint.schemaVersion ~= 2 and blueprint.schemaVersion ~= 3)
        or blueprint.pivot ~= "Model:GetPivot()" or (blueprint.schemaVersion == 2 and type(blueprint.anchor) ~= "table")
        or type(blueprint.parts) ~= "table"
        or #blueprint.parts < 1 or #blueprint.parts > MAX_PARTS then
        error("Invalid saved Collision Blueprint; Preview refused")
    end
    local CollisionGeometry = require(script.Parent.StudioLocationCollisionTransform)
    local frame = CollisionGeometry.Resolve(root, blueprint)
    -- Build the whole temporary preview first; do not remove a working preview
    -- until every new recipe has passed validation and instantiated correctly.
    local draft = Instance.new("Folder")
    draft.Name = name
    draft:SetAttribute("Game1CollisionPreviewOwned", true)
    draft:SetAttribute("Game1CollisionPreviewSlug", slug)
    local ok, failure = pcall(function()
        for _, recipe in ipairs(blueprint.parts) do
            if type(recipe) ~= "table" or type(recipe.size) ~= "table"
                or type(recipe.localCFrame) ~= "table" or #recipe.size ~= 3
                or #recipe.localCFrame ~= 12 then
                error("Malformed saved Collision Part")
            end
            local shape = recipe.shape
            local ghost: BasePart
            if shape == "Block" or shape == "Ball" or shape == "Cylinder" then
                ghost = Instance.new("Part")
                if shape == "Ball" then ghost.Shape = Enum.PartType.Ball end
                if shape == "Cylinder" then ghost.Shape = Enum.PartType.Cylinder end
            elseif shape == "Wedge" then
                ghost = Instance.new("WedgePart")
            elseif shape == "CornerWedge" then
                ghost = Instance.new("CornerWedgePart")
            else
                error("Preview accepts Part primitives only")
            end
            ghost.Name = "Preview_" .. tostring(recipe.id)
            ghost.Anchored = true
            ghost.CanCollide = false
            ghost.CanTouch = false
            ghost.CanQuery = false
            ghost.CastShadow = false
            ghost.Transparency = 1
            local targetFrame, targetSize = CollisionGeometry.Part(frame, recipe)
            ghost.Size = targetSize
            ghost.CFrame = targetFrame
            ghost.Parent = draft
            local outline = Instance.new("SelectionBox")
            outline.Name = "Game1CollisionOutline"
            outline.LineThickness = 0.035
            outline.SurfaceTransparency = 1
            outline.Color3 = Color3.fromRGB(52, 210, 179)
            outline.Adornee = ghost
            outline.Parent = ghost
        end
    end)
    if not ok then
        draft:Destroy()
        error(tostring(failure))
    end
    clearPreview(workspaceRef, name)
    draft.Parent = workspaceRef
    return #blueprint.parts
end

return function(config: any)
    local HttpService = config.HttpService
    local workspaceRef = config.Workspace
    local function handle(command: any)
        local result = {
            project = "game1", command = command.command,
            schemaVersion = 1, operationId = command.operationId,
            slug = command.slug, phase = command.phase,
            expectedRevision = command.expectedRevision,
        }
        local ok, response = pcall(function()
            if command.project ~= "game1"
                or (command.command ~= "location-collision-authoring-v1"
                    and command.command ~= "house-collision-authoring-v1")
                or command.schemaVersion ~= 1 or type(command.operationId) ~= "string"
                or type(command.slug) ~= "string" or type(command.phase) ~= "string"
                or type(command.expectedRevision) ~= "number" then
                error("Unsupported Collision Studio command; reinstall Game1Bridge")
            end
            if config.RunService:IsRunning() then error("Studio Edit mode required") end
            if command.phase == "clear-preview" then
                return {partCount = clearPreview(workspaceRef, previewName(command))}
            end
            local requiresParts = command.phase == "validate" or command.phase == "capture"
            local model, parts, ignoredGenerated = selectedModel(config.Selection, workspaceRef, command, requiresParts)
            if requiresParts then
                return {blueprint = capture(model, parts, command),
                    ignoredGenerated = ignoredGenerated}
            elseif command.phase == "preview" then
                if isHouse(command) and command.blueprint.schemaVersion ~= 3 then
                    error("House requires pivot-based Collision Blueprint v3")
                end
                return {partCount = preview(model, command.blueprint, workspaceRef, command.slug, previewName(command))}
            end
            error("Unknown Collision Studio phase")
        end)
        if ok then
            for key, value in pairs(response) do result[key] = value end
        else
            result.error = tostring(response)
        end
        local posted, answer = pcall(HttpService.RequestAsync, HttpService, {
            Url = config.bridgeUrl .. (if isHouse(command)
                then "/house-collision-result" else "/location-collision-result"),
            Method = "POST",
            Headers = { ["X-Game1-Token"] = config.bridgeToken,
                        ["Content-Type"] = "application/json" },
            Body = HttpService:JSONEncode(result),
        })
        if not posted or not answer.Success then
            warn("[Game1 Location Collision] result transport failed: " ..
                tostring(posted and answer.StatusCode or answer))
        end
    end
    return {handle = handle, dispose = function()
        for _, name in {PREVIEW_LOCATION, PREVIEW_HOUSE} do
            local ok, err = pcall(clearPreview, workspaceRef, name)
            if not ok then warn("[Game1 Collision] " .. tostring(err)) end
        end
    end}
end

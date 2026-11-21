-- Metadata-only Repair for canonical Location FBX placements.
-- RootPart, missing carrier, Bones, visual/COL topology are publication issues;
-- NEVER reconstruct them in Studio or disguise a copy as authored geometry.
local Repair = {}

local ATTRIBUTES = {
    "Game1DecoInstanceId", "Game1DecoAssetSlug", "Game1DecoRegistryModelAssetId",
    "Game1DecoPublishedModelAssetId", "Game1DecoPublishedModelSha256",
}

-- Newly issued identities must not collide with any scanned placement, even
-- when a Studio/plugin GUID provider unexpectedly repeats a value.
local function assignedId(http: any, occupied: {[string]: number}): string
    for _ = 1, 16 do
        local candidate = http:GenerateGUID(false)
        if type(candidate) == "string" and candidate ~= "" and not occupied[candidate] then
            occupied[candidate] = 1
            return candidate
        end
    end
    error("Cannot issue a unique Location Placement ID; Place unchanged")
end

local function originalState(model: Model): any
    local attrs = {}
    for _, name in ipairs(ATTRIBUTES) do attrs[name] = model:GetAttribute(name) end
    local meshes={}
    for _,obj in ipairs(model:GetDescendants()) do
        if obj:IsA("MeshPart") then
            meshes[obj]={cframe=obj.CFrame,size=obj.Size,pivotOffset=obj.PivotOffset}
        end
    end
    return {name = model.Name, attributes = attrs, pivot = model:GetPivot(),
        primary = model.PrimaryPart, parent = model.Parent, meshes=meshes, scale=model:GetScale()}
end

local function restore(model: Model, state: any)
    if model.Parent ~= state.parent then error("Repair rollback lost Location Model") end
    model.Name = state.name
    for _, name in ipairs(ATTRIBUTES) do
        model:SetAttribute(name, state.attributes[name])
    end
end

function Repair.Apply(refs: {any}, ctx: any): any
    local blocked, eligible, allIds, selectedIds, retained = {}, {}, {}, {}, {}
    local originals = ctx.allRefs or refs
    for _, ref in ipairs(originals) do
        if not ref.external then
            if type(ref.row) ~= "table" or type(ref.row.placementId) ~= "string" then
                error("Incomplete Deco Placement ID evidence; rescan before Repair")
            end
            local pid = ref.row.placementId
            if pid ~= "" then allIds[pid] = (allIds[pid] or 0) + 1 end
        end
    end
    for _, ref in ipairs(refs) do
        if ref.external then
            error("LandscapePainter does not support Place Registry Repair")
        end
        if ref.row.ambiguous then
            table.insert(blocked, ref.row.key .. ": неоднозначное происхождение")
        elseif ref.structuralState == "legacy_import_root" then
            table.insert(blocked, ref.row.key .. ": Импортный RootPart — требуется перепубликация FBX; Repair запрещён")
        elseif ref.structuralState ~= "current" then
            table.insert(blocked, ref.row.key .. ": неканонический rig " .. tostring(ref.structuralState)
                .. "; требуется перепубликация FBX, не Repair")
        elseif not ref.root or ref.root.Parent == nil then
            table.insert(blocked, ref.row.key .. ": нет подтверждённой Model, требуется публикация FBX")
        elseif ref.row.needsRig or ref.row.needsMesh then
            table.insert(blocked, ref.row.key .. ": изменение геометрии выполняется из опубликованной Model, не через Repair")
        elseif not ref.row.needsStructure and not ref.row.duplicateId then
            table.insert(blocked, ref.row.key .. ": метаданные уже актуальны")
        else
            table.insert(eligible, ref)
        end
    end
    if #eligible == 0 then
        return {changed = 0, skipped = blocked,
            note = "Repair не изменил Place; для RootPart требуется перепубликация FBX"}
    end
    for _, ref in ipairs(eligible) do
        local pid = ref.row.placementId
        if ref.row.duplicateId and (allIds[pid] or 0) < 2 then
            error("Duplicate Placement ID evidence changed; rescan before Repair")
        end
        if pid ~= "" then selectedIds[pid] = (selectedIds[pid] or 0) + 1 end
    end
    local recording = ctx.history:TryBeginRecording(ctx.recordingName, "Repair Location Placement Identity")
    if not recording then error("Studio Undo unavailable; Place unchanged") end
    local undo = {}
    local changed = 0
    local ok, problem = pcall(function()
        for _, ref in ipairs(eligible) do
            local model = ref.root
            local before = originalState(model)
            if model:GetPivot() ~= ref.rootPivot or model.PrimaryPart ~= ref.rootPrimary then
                error("Location placement changed after Scan; Place unchanged")
            end
            table.insert(undo, function() restore(model, before) end)
            local pid = ref.row.placementId
            if pid == "" then
                pid = assignedId(ctx.http, allIds)
            elseif (allIds[pid] or 0) > 1 then
                -- A single-item Repair must fix THE selected duplicate, even
                -- if it happens to be the first scanned member of the group.
                -- For a complete group Repair retain one original identity,
                -- and re-key all remaining members. Partial selection always
                -- re-keys selected members and never silently returns zero.
                if selectedIds[pid] == allIds[pid] and not retained[pid] then
                    retained[pid] = true
                else
                    pid = assignedId(ctx.http, allIds)
                end
            end
            local updates = {
                Game1DecoInstanceId = pid,
                Game1DecoAssetSlug = ref.entry.slug,
                Game1DecoRegistryModelAssetId = ref.entry.model,
                -- Current v2 geometry is already validated by Inventory.
                Game1DecoPublishedModelAssetId = ref.entry.model,
                Game1DecoPublishedModelSha256 = ref.entry.sha,
            }
            local newName = ref.entry.slug .. "__" .. pid:sub(1, 8)
            local dirty = model.Name ~= newName
            for key, value in pairs(updates) do
                if model:GetAttribute(key) ~= value then dirty = true end
            end
            if dirty then
                model.Name = newName
                for key, value in pairs(updates) do model:SetAttribute(key, value) end
                changed += 1
            end
            if model:GetPivot() ~= before.pivot or model.PrimaryPart ~= before.primary
                or model.Parent ~= before.parent or model:GetScale() ~= before.scale then
                error("Repair changed Model pivot/PrimaryPart/parent or scale; rolling back")
            end
            for obj,state in pairs(before.meshes) do
                if obj.CFrame~=state.cframe or obj.Size~=state.size
                    or obj.PivotOffset~=state.pivotOffset then
                    error("Repair changed existing MeshPart geometry or PivotOffset; rolling back")
                end
            end
        end
    end)
    if not ok then
        for i = #undo, 1, -1 do pcall(undo[i]) end
        ctx.history:FinishRecording(recording, Enum.FinishRecordingOperation.Cancel)
        error("Repair отменён: " .. tostring(problem))
    end
    ctx.history:FinishRecording(recording,
        if changed > 0 then Enum.FinishRecordingOperation.Commit
        else Enum.FinishRecordingOperation.Cancel)
    return {changed = changed, skipped = blocked, undo = changed > 0,
        note = if changed > 0 then "Исправлены только идентификаторы/имена канонических моделей"
            else "Метаданные уже актуальны; Place не изменён"}
end

return Repair

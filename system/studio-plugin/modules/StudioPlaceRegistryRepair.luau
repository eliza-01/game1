-- Metadata-only Repair for canonical Location FBX placements.
-- RootPart, missing carrier, Bones, visual/COL topology are publication issues;
-- NEVER reconstruct them in Studio or disguise a copy as authored geometry.
local Repair = {}

local ATTRIBUTES = {
    "Game1DecoInstanceId", "Game1DecoAssetSlug", "Game1DecoRegistryModelAssetId",
    "Game1DecoPublishedModelAssetId", "Game1DecoPublishedModelSha256",
}

local function assignedId(http: any): string
    return http:GenerateGUID(false)
end

local function originalState(model: Model): any
    local attrs = {}
    for _, name in ipairs(ATTRIBUTES) do attrs[name] = model:GetAttribute(name) end
    return {name = model.Name, attributes = attrs, pivot = model:GetPivot(),
        primary = model.PrimaryPart, parent = model.Parent}
end

local function restore(model: Model, state: any)
    if model.Parent ~= state.parent then error("Repair rollback lost Location Model") end
    model.Name = state.name
    for _, name in ipairs(ATTRIBUTES) do
        model:SetAttribute(name, state.attributes[name])
    end
end

function Repair.Apply(refs: {any}, ctx: any): any
    local blocked, eligible, allIds, kept = {}, {}, {}, {}
    local originals = ctx.allRefs or refs
    for _, ref in ipairs(originals) do
        local pid = ref.row.placementId
        if pid ~= "" then
            allIds[pid] = (allIds[pid] or 0) + 1
            if not kept[pid] then kept[pid] = ref end
        end
    end
    for _, ref in ipairs(refs) do
        if ref.row.ambiguous then
            table.insert(blocked, ref.row.key .. ": неоднозначное происхождение")
        elseif ref.structuralState == "legacy_import_root" then
            table.insert(blocked, ref.row.key .. ": Импортный RootPart — требуется перепубликация FBX; Repair запрещён")
        elseif ref.structuralState ~= "current" then
            table.insert(blocked, ref.row.key .. ": неканонический rig " .. tostring(ref.structuralState)
                .. "; требуется перепубликация FBX, не Repair")
        elseif not ref.root or ref.root.Parent == nil then
            table.insert(blocked, ref.row.key .. ": нет подтверждённой Model, требуется публикация FBX")
        elseif ref.needsCol or ref.row.needsRig or ref.row.needsMesh then
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
            if pid == "" or ((allIds[pid] or 0) > 1 and kept[pid] ~= ref) then
                pid = assignedId(ctx.http)
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
                or model.Parent ~= before.parent then
                error("Repair changed Model pivot/PrimaryPart/parent; rolling back")
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

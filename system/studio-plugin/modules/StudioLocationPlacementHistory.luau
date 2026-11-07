-- Per-placement, bounded authoring audit for Location repair and sync.
-- The global SQLite Place Registry journal remains authoritative for Undo;
-- this Model attribute is only a compact, inspectable provenance trail.
local History = {}

function History.Append(root: Model, http: any, slug: string, events: {any},
    beforeMeshes: {any}?, afterMeshes: {any}?)
    if #events == 0 then return end
    local data = {}
    local raw = root:GetAttribute("Game1DecoSyncHistory")
    if raw ~= nil then
        if type(raw) ~= "string" then error("invalid existing placement history") end
        local ok, decoded = pcall(http.JSONDecode, http, raw)
        if not ok or type(decoded) ~= "table" then error("corrupt existing placement history") end
        data = decoded
    end
    local item = {atUtc=os.time(),slug=slug,
        instanceId=tostring(root:GetAttribute("Game1DecoInstanceId") or ""),changes=events}
    if beforeMeshes then item.meshIdsBefore=beforeMeshes end
    if afterMeshes then item.meshIdsAfter=afterMeshes end
    table.insert(data,item)
    while #data > 12 do table.remove(data,1) end
    local output=http:JSONEncode(data)
    -- Large Mesh lists belong in the global audit, never overflow Roblox attrs.
    if #output > 30000 then
        item.meshIdsBefore=nil
        item.meshIdsAfter=nil
        item.meshHistoryInDatabase=true
        output=http:JSONEncode(data)
    end
    if #output > 30000 then error("placement history exceeds attribute limit") end
    root:SetAttribute("Game1DecoSyncHistory",output)
end

return table.freeze(History)

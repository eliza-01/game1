-- Pure display projection of the on-demand diagnostic snapshot. No runtime work.
local View = {}

local stages = {full = "Full", shell = "Shell", loading = "Loading", preparing = "Preparing", fault = "Error", unregistered = "Unknown"}
local lod = {FULL = "FULL", LOD1 = "LOD1", UNLOADED = "Hidden", UNTRACKED = "Waiting"}

local function rowText(row)
    local stage = stages[row.server] or row.server
    local state = lod[row.actual] or row.actual
    local distance = row.distance and string.format("%.0f studs", row.distance) or "Distance unknown"
    local title = string.format("%s · %s", row.name, distance)
    local status = state
    if row.actual ~= row.desired and row.desired ~= "-" then
        status = status .. " → " .. (lod[row.desired] or row.desired)
    end
    status = status .. "  |  Server: " .. stage
    local resources = string.format("Client: %d meshes · %d bones · %d animators", row.meshes, row.bones, row.animators)
    local server = string.format("Server hitboxes %d", row.hitboxes)
    if row.server == "shell" then
        if row.audit == "shell M0 B0 A0 H0" then
            server = server .. " · Released at transition"
        elseif row.audit then
            server = server .. " · Check shell audit"
        else
            server = server .. " · No audit"
        end
    elseif row.actual ~= row.desired or row.reason ~= "distance" then
        server = server .. " · " .. row.reason
    end
    return {title=title, status=status, resources=resources, server=server}
end

function View.Build(snapshot, enabled, reason)
    local result = {summary = {"Server rig demand: " .. (enabled and "ON" or "OFF")}, groups = {}}
    if not snapshot then
        result.summary[#result.summary + 1] = tostring(reason or "No snapshot")
        return result
    end
    local c, sc = snapshot.counts, snapshot.serverCounts
    local monsters, npcs = {}, {}
    local meshes, bones, animators, boxes, released = 0, 0, 0, 0, 0
    for _, row in ipairs(snapshot.rows) do
        meshes = meshes + row.meshes
        bones = bones + row.bones
        animators = animators + row.animators
        boxes = boxes + row.hitboxes
        if row.server == "shell" and row.audit == "shell M0 B0 A0 H0" then released = released + 1 end
        local group = row.kind == "Monster" and monsters or npcs
        group[#group + 1] = rowText(row)
    end
    local summary = result.summary
    summary[#summary + 1] = string.format("Observed: %d  |  Monsters %d  ·  NPC %d", #snapshot.rows, #monsters, #npcs)
    summary[#summary + 1] = string.format("FULL %d  ·  LOD1 %d  ·  Hidden %d  ·  Wait %d", c.FULL, c.LOD1, c.UNLOADED, c.UNTRACKED)
    summary[#summary + 1] = string.format("Server: Full %d  ·  Shell %d  ·  Loading %d", sc.full, sc.shell, sc.loading + sc.preparing)
    if sc.fault + sc.unregistered > 0 then
        summary[#summary + 1] = string.format("Server: Error %d  ·  Unknown %d", sc.fault, sc.unregistered)
    end
    summary[#summary + 1] = string.format("Client: %d meshes · %d bones · %d animators", meshes, bones, animators)
    summary[#summary + 1] = string.format("Server hitboxes: %d", boxes)
    summary[#summary + 1] = sc.shell > 0 and string.format("Shells released: %d/%d (last transition)", released, sc.shell) or "Shell release: not observed"
    if snapshot.waitingForPlayerRoot then summary[#summary + 1] = "Waiting for player" end
    result.groups = {{name="Monsters", rows=monsters}, {name="NPC", rows=npcs}}
    return result
end
return View

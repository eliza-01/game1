-- Published-model provenance and shape policy for Location Assets.
-- Model Asset IDs identify immutable publications. A visual MeshId can stay
-- unchanged when a new publication adds a collider or other rig parts.
-- Used only by Location Place Registry; no geometry writes in this module.
local History = require(script.Parent.StudioPublishedMeshHistory)
local Published = {}

local function current(entry: any): any?
    for _, version in ipairs(entry.models) do
        if version.modelAssetId == entry.model then return version end
    end
    return nil
end

function Published.Current(entry: any): any?
    return current(entry)
end

function Published.VisualCurrent(entry: any, meshId: string): boolean
    local version = current(entry)
    if not version then return false end
    for _, mesh in ipairs(version.meshes) do
        if mesh.meshId == meshId and type(mesh.visualNames) == "table" and #mesh.visualNames > 0 then
            return true
        end
    end
    return false
end

function Published.CurrentShape(entry: any, root: Model?): boolean
    local version = current(entry)
    return root ~= nil and version ~= nil and History.MatchesInventory(root, version)
end

-- A stamped old Model ID is corroborating evidence only when its COMPLETE
-- MeshPart inventory matches the placed Model. Never trust a copied stamp alone.
function Published.ResolveOldVersion(entry: any, root: Model?, visualMeshId: string): (string, boolean)
    local matches = {}
    for _, version in ipairs(entry.models) do
        local found = false
        if root then
            found = History.MatchesInventory(root, version)
        else
            for _, mesh in ipairs(version.meshes) do
                if mesh.meshId == visualMeshId and type(mesh.visualNames) == "table"
                    and #mesh.visualNames > 0 then
                    found = true
                    break
                end
            end
        end
        if found then table.insert(matches, version.modelAssetId) end
    end
    if #matches == 1 then return matches[1], false end
    if root and #matches > 1 then
        local stamped = tostring(root:GetAttribute("Game1DecoPublishedModelAssetId") or "")
        for _, candidate in ipairs(matches) do
            if candidate == stamped then return candidate, false end
        end
    end
    return "", true
end

return table.freeze(Published)

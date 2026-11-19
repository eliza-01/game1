-- Resolve the binding root of reused NPC clips before any AnimationTrack loads.
-- Roblox bone clips also bind through the skinned MeshPart's name; matching
-- Bone names alone does not guarantee that the root Bone receives its keys.
-- Published templates are read-only. Only the spawned runtime clone is adapted.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local NpcRegistry = require(Shared:WaitForChild("npc"):WaitForChild("NpcRegistry"))
local Compatibility = require(Shared:WaitForChild("animation"):WaitForChild("AnimationCompatibility"))

local NpcAnimationRigBinding = {}
local sourceRoots: {[string]: {name: string, skeleton: string}?} = {}

local function rigRoot(visual: Instance): MeshPart?
    local result: MeshPart? = nil
    for _, descendant in ipairs(visual:GetDescendants()) do
        if descendant:IsA("Bone") and descendant.Parent and descendant.Parent:IsA("MeshPart") then
            local parent = descendant.Parent :: MeshPart
            if result and result ~= parent then
                return nil -- Multiple independently skinned roots cannot be renamed safely.
            end
            result = parent
        end
    end
    return result
end

-- MeshPart names must not influence the structural compatibility comparison.
local function skeletonKey(visual: Instance): string
    local paths = {}
    for _, descendant in ipairs(visual:GetDescendants()) do
        if descendant:IsA("Bone") then
            local names = {descendant.Name}
            local parent = descendant.Parent
            while parent and parent:IsA("Bone") do
                table.insert(names, 1, parent.Name)
                parent = parent.Parent
            end
            table.insert(paths, table.concat(names, "/"))
        end
    end
    table.sort(paths)
    return table.concat(paths, "|")
end

local function templateFor(slug: string): Model?
    local definition = (NpcRegistry.npcs or {})[slug]
    if not definition then return nil end
    local components = string.split(tostring(definition.serverStoragePath or ""), ".")
    if components[1] ~= "ServerStorage" then return nil end
    local current: Instance? = ServerStorage
    for index = 2, #components do
        current = if current then current:FindFirstChild(components[index]) else nil
        if not current then return nil end
    end
    return if current and current:IsA("Model") then current else nil
end

local function sourceRoot(slug: string): {name: string, skeleton: string}?
    if sourceRoots[slug] then return sourceRoots[slug] end
    local template = templateFor(slug)
    if not template then return nil end -- Do not cache missing templates across Studio sync.
    local visual = template:FindFirstChild("ImportedRig") or template
    local root = rigRoot(visual)
    if not root then return nil end
    local result = {name = root.Name, skeleton = skeletonKey(visual)}
    sourceRoots[slug] = result
    return result
end

function NpcAnimationRigBinding.Align(visual: Model, recipientSlug: string, profile: any?, weaponSet: string): boolean
    if not profile or not profile.slots then return true end
    local required = {}
    for _, rows in pairs(profile.slots) do
        if typeof(rows) == "table" then
            for _, row in ipairs(rows) do
                if Compatibility.Allowed(row, weaponSet) then
                    local source = tostring(row.sourceNpc or "")
                    if source == "" then
                        warn("[game1][npc] animation origin is missing for " .. recipientSlug .. "; export NPC animations again")
                        return false
                    end
                    required[source] = true
                end
            end
        end
    end
    if next(required) == nil then return true end

    local root = rigRoot(visual)
    if not root then
        warn("[game1][npc] missing or ambiguous skinned root for " .. recipientSlug)
        return false
    end
    local targetSkeleton = skeletonKey(visual)
    local requiredName: string? = nil
    for slug in pairs(required) do
        local origin = sourceRoot(slug)
        if not origin then
            warn("[game1][npc] animation source rig is unavailable: " .. slug .. " -> " .. recipientSlug)
            return false
        end
        if origin.skeleton ~= targetSkeleton then
            warn("[game1][npc] animation bone hierarchy differs: " .. slug .. " -> " .. recipientSlug)
            return false
        end
        if requiredName and requiredName ~= origin.name then
            warn("[game1][npc] animations require different mesh root names on " .. recipientSlug
                .. "; connect clips authored for one root or republish them against a shared canonical rig")
            return false
        end
        requiredName = origin.name
    end
    if requiredName and root.Name ~= requiredName then
        root:SetAttribute("Game1OriginalMeshName", root.Name)
        root.Name = requiredName
    end
    return true
end

return table.freeze(NpcAnimationRigBinding)

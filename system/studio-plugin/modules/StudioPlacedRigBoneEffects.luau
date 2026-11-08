-- Placement-owned visual decorations attached to authored Bones. Accept either
-- leaf effects directly under a Bone or one Attachment under a Bone containing
-- ONLY leaf effects. Keep the Attachment as a unit: its CFrame/Axis and its
-- children's properties must survive the managed rig swap unchanged.
-- Arbitrary descendants, scripts and geometry are never portable.
local BoneEffects = {}

local MAX_EFFECTS_PER_RIG = 128

local function isLeafEffect(item: Instance): boolean
    return #item:GetChildren() == 0
        and (item:IsA("ParticleEmitter") or item:IsA("PointLight")
            or item:IsA("SpotLight") or item:IsA("SurfaceLight"))
end

-- Only top-level decorations are portable. An effect below an Attachment is
-- intentionally NOT portable on its own, so it is never cloned twice or
-- detached from the authored Attachment transform.
function BoneEffects.IsPortable(item: Instance): boolean
    if item.Parent == nil or not item.Parent:IsA("Bone") then return false end
    if isLeafEffect(item) then return true end
    -- Bone inherits Attachment in Roblox: accept only the concrete class.
    -- Otherwise a nested Bone with effects could be mistaken for decoration.
    if item.ClassName ~= "Attachment" then return false end
    for _, child in ipairs(item:GetChildren()) do
        if not isLeafEffect(child) then return false end
    end
    return true
end

local function boneKey(bone: Bone): string
    local names = {}
    local cursor: Instance? = bone
    while cursor and cursor:IsA("Bone") do
        table.insert(names, 1, cursor.Name)
        cursor = cursor.Parent
    end
    return table.concat(names, "\0")
end

local function bones(roots: {Instance}): {[string]: Bone}
    local result = {}
    for _, root in ipairs(roots) do
        for _, item in ipairs(root:GetDescendants()) do
            if item:IsA("Bone") then
                local key = boneKey(item)
                if result[key] then
                    error("ambiguous duplicated Bone path in Location rig: " .. item.Name)
                end
                result[key] = item
            end
        end
    end
    return result
end

-- Called only AFTER StudioPublishedMeshHistory.VerifyChildren has proved the
-- outgoing physical rig and its non-effect descendants. This clones, never
-- moves, each top-level effect/Attachment onto the staged rig. Until the
-- managed swap finalizes, old effects remain untouched for rollback. If a
-- Bone no longer exists, refuse the swap rather than losing or misplacing it.
function BoneEffects.CopyToIncoming(outgoing: {Instance}, incoming: {Instance}): number
    local portable = {}
    local nodeCount = 0
    for _, root in ipairs(outgoing) do
        for _, item in ipairs(root:GetDescendants()) do
            if BoneEffects.IsPortable(item) then
                table.insert(portable, item)
                -- Count both parent Attachments and their child effects.
                -- The rigid whitelist above limits attachment depth to one.
                nodeCount += 1 + #item:GetChildren()
                if nodeCount > MAX_EFFECTS_PER_RIG then
                    error("too many placed Bone decorations to transfer; no Place geometry modified")
                end
            end
        end
    end
    if #portable == 0 then return 0 end
    -- Do not inspect/match Bone paths for ordinary rigs without decorations.
    local oldBones = bones(outgoing)
    local newBones = bones(incoming)
    local copied = 0
    for _, item in ipairs(portable) do
        local parent = item.Parent :: Bone
        local key = boneKey(parent)
        if oldBones[key] ~= parent then
            error("ambiguous placed Bone effect owner: " .. parent.Name)
        end
        local destination = newBones[key]
        if not destination then
            error("placed Bone decoration " .. item.Name .. " cannot follow missing Bone "
                .. parent.Name .. "; no Place geometry modified")
        end
        if destination:FindFirstChild(item.Name) then
            error("placed Bone decoration name conflicts with new publication: " .. item.Name
                .. "; no Place geometry modified")
        end
        copied += 1
        local clone = item:Clone()
        if not clone then
            error("placed Bone decoration is not cloneable: " .. item.Name
                .. "; no Place geometry modified")
        end
        clone.Parent = destination
    end
    return copied
end

return table.freeze(BoneEffects)

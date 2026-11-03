-- Resolves the authoring rig's upper-body branch without gender/asset-name rules.
-- The first spine segment stays with locomotion. Its spine child is the bridge;
-- the pelvis and leg branches must remain outside that subtree.
local CharacterUpperBodyRig = {}

local LOWER_BODY_TOKENS = table.freeze({
    "pelvis", "hip", "thigh", "shin", "calf", "foot", "toe", "leg",
})

local function isSpineBone(bone: Instance?): boolean
    if not bone or not bone:IsA("Bone") then
        return false
    end
    local name = string.lower(bone.Name)
    return name == "spine"
        or string.match(name, "^spine[._]%d+$") ~= nil
end

local function hasLowerBodyDescendants(bridge: Bone): (boolean, string?)
    for _, descendant in bridge:GetDescendants() do
        if descendant:IsA("Bone") then
            local name = string.lower(descendant.Name)
            for _, token in LOWER_BODY_TOKENS do
                if string.find(name, token, 1, true) then
                    return true, descendant.Name
                end
            end
        end
    end
    return false, nil
end

function CharacterUpperBodyRig.ResolveBridge(visual: Model): (Bone?, string?)
    -- The two currently registered skeletons have different naming conventions:
    -- female spine -> spine.001, male pelvis -> spine_01 -> spine_02.
    -- Resolve the *chain*, not its spelling. The second spine segment starts
    -- the attack/aim subtree for either skeleton.
    local candidate: Bone? = nil
    for _, descendant in visual:GetDescendants() do
        if isSpineBone(descendant) then
            local parent = descendant.Parent
            if isSpineBone(parent) then
                local grandparent = parent.Parent
                if not isSpineBone(grandparent) then
                    if candidate then
                        return nil, "multiple upper-body spine branches found"
                    end
                    candidate = descendant :: Bone
                end
            end
        end
    end
    if not candidate then
        return nil, "upper-body spine chain was not found (requires two connected spine bones)"
    end
    local hasLower, lowerName = hasLowerBodyDescendants(candidate)
    if hasLower then
        return nil, "upper-body bridge includes lower-body bone: " .. tostring(lowerName)
    end
    return candidate, nil
end

return table.freeze(CharacterUpperBodyRig)

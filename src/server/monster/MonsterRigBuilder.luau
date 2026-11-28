-- Monster-specific animation root compatibility. Shell and visual attachment are shared by MNPC.
local MonsterRigBuilder = {}

local function ensureRuntimeAnimationRoot(visual: Model): number
    -- Studio's Animation Editor exports skinned FBX clips with a synthetic
    -- RootBone pose above the authored skeleton root. Runtime Animator ignores
    -- animation on a Bone that is itself the root of a MeshPart hierarchy.
    -- Materialize that neutral RootBone in the runtime clone so the authored
    -- root bone (for example `spine`) becomes an ordinary animated child.
    --
    -- The helper is identity-only and is added before tracks are loaded. Existing
    -- authored Bone world/rest transforms are therefore unchanged. The navigation
    -- wrapper remains responsible only for world locomotion/yaw; animation owns
    -- the complete authored bone pose, including root-bone translation/rotation.
    local bridged = 0
    for _, descendant in ipairs(visual:GetDescendants()) do
        if descendant:IsA("MeshPart") then
            local directBones = {}
            local animationRoot: Bone? = nil
            for _, child in ipairs(descendant:GetChildren()) do
                if child:IsA("Bone") then
                    if child.Name == "RootBone" then
                        animationRoot = child
                    else
                        table.insert(directBones, child)
                    end
                end
            end

            if #directBones > 0 then
                if not animationRoot then
                    animationRoot = Instance.new("Bone")
                    animationRoot.Name = "RootBone"
                    animationRoot.CFrame = CFrame.identity
                    animationRoot.Parent = descendant
                    animationRoot:SetAttribute("Game1RuntimeAnimationRoot", true)
                    bridged += 1
                end

                for _, bone in ipairs(directBones) do
                    -- Preserve the authored rest/world transform even if a source
                    -- asset already supplied a non-identity RootBone.
                    local authoredMeshLocal = bone.CFrame
                    bone.Parent = animationRoot
                    bone.CFrame = animationRoot.CFrame:Inverse() * authoredMeshLocal
                end
            end
        end
    end

    visual:SetAttribute("Game1RuntimeAnimationRootBridgeCount", bridged)
    return bridged
end

MonsterRigBuilder.EnsureRuntimeAnimationRoot = ensureRuntimeAnimationRoot
return table.freeze(MonsterRigBuilder)

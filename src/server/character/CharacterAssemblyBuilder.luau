--!strict
-- Builds an unparented template. Asset loading/cache and gameplay physics stay
-- with CharacterService/CharacterRigService. No animation or inventory writes.
local CharacterAtlasBinder = require(script.Parent:WaitForChild("CharacterAtlasBinder"))
local Builder = {}
local slots = { "upper", "lower", "gloves", "boots", "head", "eyes", "eyebrows", "hair" }
local HAIR_GRIP_NAME = "CharacterMount"

local function meshFromAsset(asset: Model, expectedName: string): MeshPart
    local meshes = {}
    for _, object in asset:GetDescendants() do
        if object:IsA("MeshPart") then table.insert(meshes, object) end
    end
    assert(#meshes == 1, expectedName .. ": expected exactly one MeshPart")
    assert(meshes[1].Name == expectedName, expectedName .. ": unexpected imported mesh name")
    return meshes[1]:Clone()
end

local function bonesIn(mesh: MeshPart): { [string]: Bone }
    local found = {}
    for _, object in mesh:GetDescendants() do
        if object:IsA("Bone") then
            assert(found[object.Name] == nil, "duplicate bone: " .. object.Name)
            found[object.Name] = object
        end
    end
    return found
end

local function configure(mesh: BasePart)
    mesh.Anchored = false
    mesh.CanCollide = false
    mesh.CanTouch = false
    mesh.CanQuery = false
    mesh.Massless = true
end

local function targetSocketCFrame(targetBone: Bone): CFrame
    local parent = targetBone.Parent
    if parent and parent:IsA("Bone") then
        return parent.TransformedWorldCFrame * targetBone.CFrame
    end
    return targetBone.WorldCFrame
end

local function createCanonicalHairGrip(mesh: MeshPart): Attachment
    -- Match the weapon attachment contract: preserve the authored grip point,
    -- while the grip basis stays in world XYZ instead of inheriting PivotOffset.
    local gripPoint = mesh:GetPivot().Position
    local grip = Instance.new("Attachment")
    grip.Name = HAIR_GRIP_NAME
    grip.CFrame = mesh.CFrame:ToObjectSpace(CFrame.new(gripPoint))
    grip:SetAttribute("Game1HairGrip", true)
    grip.Parent = mesh
    return grip
end

local function alignHairToSocket(mesh: MeshPart, grip: Attachment, socketFrame: CFrame)
    local delta = socketFrame * grip.WorldCFrame:Inverse()
    mesh:PivotTo(delta * mesh:GetPivot())
end

function Builder.Build(recipe: any, loadAsset: (number) -> Model?): Model
    assert(recipe and recipe.schema_version == 1 and recipe.ready == true, "assembly is not ready")
    local wrapper = Instance.new("Model")
    wrapper.Name = "assembled_character"
    local ok, reason = pcall(function()
        local imported = Instance.new("Model")
        imported.Name = "ImportedRig"
        imported.Parent = wrapper
        local rawCore = loadAsset(assert(tonumber(recipe.rig.asset_id), "invalid rig asset ID"))
        assert(rawCore, "cannot load rig")
        local carrier = meshFromAsset(rawCore, "rig_carrier")
        carrier.Parent = imported
        configure(carrier)
        carrier.Transparency = 1
        carrier.CastShadow = false
        local canonical = bonesIn(carrier)
        for _, name in recipe.rig.bone_names do assert(canonical[name], "core is missing bone " .. name) end

        local root = Instance.new("Part")
        root.Name = "RootPart"
        root.Size = Vector3.new(0.35, 0.03, 0.35)
        root.CFrame = CFrame.identity
        root.Transparency = 1
        root.CastShadow = false
        configure(root)
        root.Parent = imported
        local coreWeld = Instance.new("WeldConstraint")
        coreWeld.Name = "CoreRootWeld"
        coreWeld.Part0 = root
        coreWeld.Part1 = carrier
        coreWeld.Parent = root
        for _, slot in slots do
            local part = assert(recipe.parts[slot], "missing slot " .. slot)
            local raw = loadAsset(assert(tonumber(part.asset_id), "invalid part asset ID"))
            assert(raw, "cannot load " .. part.id)
            local mesh = meshFromAsset(raw, part.id)
            mesh.Parent = imported -- shared skinning requires the same Model
            configure(mesh)
            mesh:SetAttribute("CharacterPartSlot", slot)
            mesh:SetAttribute("CharacterPartId", part.id)
            local incoming = bonesIn(mesh)
            if part.attachment ~= "" then
                local target = assert(canonical[part.attachment], "missing attachment " .. part.attachment)
                local anchor: Attachment
                local runtimeHairGrip = false
                if part.attachment_mode == "pivot" then
                    assert(slot == "hair" and part.attachment == "hair_mount", "invalid rigid hair mount")
                    assert(#part.used_bones == 0 and next(incoming) == nil, "rigid hair must not contain skin bones")
                    anchor = createCanonicalHairGrip(mesh)
                    alignHairToSocket(mesh, anchor, targetSocketCFrame(target))
                    mesh.Anchored = true
                    mesh:SetAttribute("Game1HairAttachment", true)
                    mesh:SetAttribute("HairTargetBoneName", target.Name)
                    mesh:SetAttribute("HairAttachmentMode", "runtime-canonical-grip-v1")
                    runtimeHairGrip = true
                else
                    -- Backward compatible: older hair rigs use a socket Bone.
                    local socket = assert(incoming[part.socket_bone], "missing accessory socket")
                    mesh.CFrame = target.WorldCFrame * socket.WorldCFrame:Inverse() * mesh.CFrame
                    anchor = Instance.new("Attachment")
                    anchor.Name = HAIR_GRIP_NAME
                    anchor.CFrame = mesh.CFrame:ToObjectSpace(target.WorldCFrame)
                    anchor.Parent = mesh
                end
                if not runtimeHairGrip then
                    local joint = Instance.new("RigidConstraint")
                    joint.Name = "CharacterMountJoint"
                    joint.Attachment0 = target
                    joint.Attachment1 = anchor
                    joint.Parent = mesh
                end
            else
                -- Import quantization can remove negligible influences and their
                -- Bone instances. Validate the imported skeleton, not the source
                -- FBX influence list; the complete skeleton lives on the carrier.
                local firstName: string? = nil
                for _, name in part.used_bones do
                    assert(canonical[name], "missing core bone " .. name)
                    if incoming[name] and firstName == nil then firstName = name end
                end
                assert(firstName, "part has no imported bind reference: " .. part.id)
                local first = incoming[firstName :: string]
                local target = assert(canonical[firstName], "unknown bind reference")
                mesh.CFrame = target.WorldCFrame * first.WorldCFrame:Inverse() * mesh.CFrame
                for name, sourceBone in incoming do
                    local targetBone = assert(canonical[name], "missing core bone " .. name)
                    local delta = targetBone.WorldCFrame:ToObjectSpace(sourceBone.WorldCFrame)
                    local _, angle = delta:ToAxisAngle()
                    assert(delta.Position.Magnitude < 0.005 and math.abs(angle) < 0.005, "incompatible bind for " .. name)
                end
                for _, bone in incoming do bone:Destroy() end
                local weld = Instance.new("Weld")
                weld.Name = "CharacterSkinWeld"
                weld.Part0 = carrier
                weld.Part1 = mesh
                weld.C0 = carrier.CFrame:ToObjectSpace(mesh.CFrame)
                weld.C1 = CFrame.identity
                weld.Parent = mesh
            end
            CharacterAtlasBinder.Apply(mesh, part.atlas_image_id)
        end
        imported.PrimaryPart = root
        wrapper.PrimaryPart = root
        local host = Instance.new("AnimationController")
        host.Name = "AnimationController"
        host.Parent = wrapper
        Instance.new("Animator").Parent = host
        wrapper:SetAttribute("CharacterAssemblyFingerprint", recipe.fingerprint)
    end)
    if not ok then wrapper:Destroy(); error(tostring(reason), 2) end
    return wrapper
end

return table.freeze(Builder)

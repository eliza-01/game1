-- Canonical Location-only rig carrier policy. Imported FBX mesh; never synthetic.
-- Character and Real Estate have their own domain assembly rules.
local Carrier = {}

function Carrier.IsCarrier(part: Instance): boolean
    return part:IsA("MeshPart") and part.Name == "rig_carrier"
end

function Carrier.IsVisual(part: MeshPart, physics: any): boolean
    return not Carrier.IsCarrier(part)
        and not physics.IsCollider(part.Name)
        and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
end

local function boneRows(root: Instance): {[string]: string}
    local rows = {}
    for _, obj in ipairs(root:GetDescendants()) do
        if obj:IsA("Bone") then
            if rows[obj.Name] ~= nil then
                error("rig_carrier contains duplicate Bone: " .. obj.Name)
            end
            local parent = obj.Parent
            rows[obj.Name] = if parent:IsA("Bone") then parent.Name else ""
        end
    end
    return rows
end

-- Static Location: no skeleton and no carrier. Skinned Location: the only
-- canonical Bone owner is one Blender-authored rig_carrier. Never synthesize it
-- or reparent Bones into a visual MeshPart on a placed asset.
local function isStaticManifest(manifest: any): boolean
    return type(manifest) == "table" and manifest.rigKind == "static"
        and manifest.carrierName == nil and type(manifest.bones) == "table"
        and #manifest.bones == 0
end

function Carrier.HasAuthoredManifest(manifest: any): boolean
    if type(manifest) ~= "table" or manifest.schemaVersion ~= 2
        or type(manifest.parts) ~= "table" or type(manifest.bones) ~= "table"
        or type(manifest.structuralHash) ~= "string" or #manifest.structuralHash ~= 64 then
        return false
    end
    if isStaticManifest(manifest) then
        for _, part in ipairs(manifest.parts) do
            if part.role == "rig_carrier" or part.name == "rig_carrier" then return false end
        end
        return true
    end
    -- Older authored v2 manifests had no rigKind, but always contained Bones.
    return (manifest.rigKind == nil or manifest.rigKind == "skinned")
        and manifest.carrierName == "rig_carrier" and #manifest.bones > 0
end

function Carrier.IsCanonicalPublication(manifest: any, legacyStatic: boolean?): boolean
    return Carrier.HasAuthoredManifest(manifest) or legacyStatic == true
end

local function validateStatic(model: Model)
    local visuals = 0
    for _, child in ipairs(model:GetDescendants()) do
        if child:IsA("Motor6D") then
            error("static Location publication unexpectedly contains Motor6D")
        elseif child:IsA("Bone") then
            error("static Location publication unexpectedly contains Bones")
        elseif child.Name == "rig_carrier" then
            error("static Location publication must not contain rig_carrier")
        elseif child:IsA("MeshPart") and child.Name ~= "col_mesh"
            and child.Name:sub(1, 4) ~= "col_" then
            visuals += 1
        end
    end
    if visuals == 0 then error("static Location publication has no visual MeshPart") end
end

-- Roblox may add a Motor6D assembly when it imports a multipart skinned FBX,
-- even though the authored FBX contains only Meshes, an Armature and Bones.
-- It is publication structure, not evidence of the legacy RootPart layout, if
-- and only if both endpoints are manifest MeshParts inside this one Model.
local function validateImporterMotors(model: Model, manifest: any,
    expected: {[string]: string})
    local pairsSeen = {}
    local partCount = 0
    for _ in pairs(expected) do partCount += 1 end
    local motorCount = 0
    for _, child in ipairs(model:GetDescendants()) do
        if child:IsA("Motor6D") then
            if isStaticManifest(manifest) then
                error("static Location publication unexpectedly contains Motor6D")
            end
            local part0, part1 = child.Part0, child.Part1
            if not part0 or not part1 or part0 == part1
                or not part0:IsA("MeshPart") or not part1:IsA("MeshPart")
                or not part0:IsDescendantOf(model) or not part1:IsDescendantOf(model)
                or expected[part0.Name] == nil or expected[part1.Name] == nil then
                error("published Location asset contains unsafe importer Motor6D: " .. child.Name)
            end
            local first, second = part0.Name, part1.Name
            if second < first then first, second = second, first end
            local key = first .. "\0" .. second
            if pairsSeen[key] then
                error("published Location asset contains duplicate importer Motor6D pair")
            end
            pairsSeen[key] = true
            motorCount += 1
        end
    end
    -- A valid imported assembly is a forest/tree over the published parts. A
    -- cycle or parallel edge can constrain transforms unpredictably.
    if motorCount >= partCount then
        error("published Location asset contains cyclic importer Motor6D assembly")
    end
end

function Carrier.Validate(model: Model, manifest: any, legacyStatic: boolean?): MeshPart?
    if not Carrier.IsCanonicalPublication(manifest, legacyStatic) then
        error("Location publication is missing its canonical FBX structure; republish if it has Bones")
    end
    for _, child in ipairs(model:GetDescendants()) do
        if child.Name == "RootPart" then
            error("published Location asset contains RootPart; republish FBX")
        end
    end
    if legacyStatic == true and not Carrier.HasAuthoredManifest(manifest) then
        validateStatic(model)
        return nil
    end
    local static = isStaticManifest(manifest)
    local actualCarrier: MeshPart? = nil
    local expected, seen = {}, {}
    for _, part in ipairs(manifest.parts) do
        if type(part.name) ~= "string" or type(part.role) ~= "string"
            or expected[part.name] ~= nil then
            error("invalid/duplicate Location publication manifest role")
        end
        expected[part.name] = part.role
    end
    validateImporterMotors(model, manifest, expected)
    for _, child in ipairs(model:GetDescendants()) do
        if child:IsA("MeshPart") then
            if seen[child.Name] then error("duplicate published Location MeshPart name") end
            seen[child.Name] = true
            local role = if Carrier.IsCarrier(child) then "rig_carrier"
                elseif child.Name == "col_mesh" or child.Name:sub(1,4) == "col_" then "collider"
                else "visual"
            if expected[child.Name] ~= role then
                error("published Location MeshPart role differs from authored manifest: " .. child.Name)
            end
            if Carrier.IsCarrier(child) then
                if actualCarrier then error("multiple published rig_carrier MeshParts") end
                if child.Parent ~= model then error("rig_carrier must be a direct child of Location Model") end
                actualCarrier = child
            end
        end
    end
    for name in pairs(expected) do
        if not seen[name] then error("published Location mesh missing: " .. name) end
    end
    if static then
        if actualCarrier then error("static Location has an unexpected rig_carrier") end
        validateStatic(model)
        return nil
    end
    if not actualCarrier or not actualCarrier.MeshId:match("%d+$") then
        error("published Location rig_carrier has no genuine MeshPart MeshId")
    end
    for _,obj in ipairs(model:GetDescendants()) do
        if obj:IsA("Bone") and not obj:IsDescendantOf(actualCarrier) then
            error("Bone outside published rig_carrier: " .. obj.Name)
        end
    end
    local rows = boneRows(actualCarrier)
    local count = 0
    for _,bone in ipairs(manifest.bones) do
        if type(bone.name) ~= "string" or rows[bone.name] ~= (bone.parent or "") then
            error("published Bone hierarchy differs from authoring manifest: " .. tostring(bone.name))
        end
        count += 1
    end
    local actual = 0
    for _ in pairs(rows) do actual += 1 end
    if actual ~= count then error("published rig_carrier lost Bones on import") end
    return actualCarrier
end

function Carrier.Diagnose(model: Model, manifest: any, legacyStatic: boolean?): string
    if model:FindFirstChild("RootPart") then return "legacy_import_root" end
    if not Carrier.IsCanonicalPublication(manifest, legacyStatic) then
        return "manual_review_required"
    end
    local carrierCount = 0
    local carrier: Instance? = nil
    for _, obj in ipairs(model:GetDescendants()) do
        if obj.Name == "rig_carrier" then
            carrierCount += 1
            carrier = obj
        end
    end
    if carrierCount > 1 then return "multiple_rig_carriers" end
    local static = isStaticManifest(manifest) or (legacyStatic == true and not Carrier.HasAuthoredManifest(manifest))
    if static and carrierCount > 0 then return "invalid_rig_carrier" end
    if not static and carrierCount == 0 then return "missing_rig_carrier" end
    if not static and (not carrier or not carrier:IsA("MeshPart")) then return "invalid_rig_carrier" end
    local ok, err = pcall(Carrier.Validate, model, manifest, legacyStatic)
    if ok then return "current" end
    local detail = tostring(err)
    if detail:find("Bone", 1, true) then return "bone_manifest_mismatch" end
    return "published_structure_mismatch"
end

function Carrier.Prepare(carrier: MeshPart)
    if not Carrier.IsCarrier(carrier) or not carrier.MeshId:match("%d+$") then
        error("synthetic or wrongly named Location rig_carrier forbidden")
    end
    carrier.Transparency = 1
    carrier.CastShadow = false
    carrier.CanCollide = false
    carrier.CanTouch = false
    carrier.CanQuery = false
    carrier.Massless = true
    carrier.TextureID = ""
    local surface = carrier:FindFirstChildOfClass("SurfaceAppearance")
    if surface then surface:Destroy() end
    carrier:SetAttribute("Game1LocationRigCarrier", true)
end

return table.freeze(Carrier)

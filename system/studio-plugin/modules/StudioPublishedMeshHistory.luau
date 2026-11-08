local Carrier = require(script.Parent.StudioLocationRigCarrier)
-- ID provenance of published Model assets. Real Estate and Location Assets
-- both keep StudioManagedRigSwap as the sole child-rig transaction.
local MeshPhysics = require(script.Parent.StudioMeshPhysicsCore)
local Ownership = require(script.Parent.StudioLocationPlacementOwner)
local BoneEffects = require(script.Parent.StudioPlacedRigBoneEffects)
local Inventory = {}

function Inventory.Id(value: any): string
    return tostring(value or ""):match("(%d+)$") or ""
end

function Inventory.Parts(root: Instance): {MeshPart}
    local parts = {}
    for _, item in ipairs(root:GetDescendants()) do
        if item:IsA("MeshPart") then table.insert(parts, item) end
    end
    return parts
end

function Inventory.Describe(modelId: string, model: Model): any
    local counts,visualNames = {},{}
    for _, part in ipairs(Inventory.Parts(model)) do
        local mid = Inventory.Id(part.MeshId)
        if mid ~= "" then
            counts[mid] = (counts[mid] or 0) + 1
            if not Carrier.IsCarrier(part) and not MeshPhysics.IsCollider(part.Name)
                and part:GetAttribute("Game1DecoPhysicsOnly") ~= true then
                visualNames[mid] = visualNames[mid] or {}
                visualNames[mid][string.sub(part.Name,1,128)] = true
            end
        end
    end
    local meshes = {}
    for mid, count in pairs(counts) do
        local names={}
        for name in pairs(visualNames[mid] or {}) do table.insert(names,name) end
        table.sort(names)
        table.insert(meshes,{meshId=mid,count=count,visualNames=names})
    end
    table.sort(meshes, function(a,b) return a.meshId<b.meshId end)
    return {modelAssetId=modelId,meshes=meshes}
end

-- A historical publication is a candidate ONLY when the entire Mesh ID
-- multiset of the placed instance agrees with the saved publication. A shared
-- collider ID or one overlapping visual mesh is not proof of provenance.
function Inventory.MatchesInventory(placed: Model, inventory: any): boolean
    if type(inventory) ~= "table" or type(inventory.meshes) ~= "table" then return false end
    local actual = Inventory.Describe("", placed).meshes
    local expected = {}
    for _, entry in ipairs(inventory.meshes) do
        if type(entry.meshId) ~= "string" or type(entry.count) ~= "number" then return false end
        if expected[entry.meshId] ~= nil or entry.count < 1 then return false end
        expected[entry.meshId] = entry.count
    end
    if #actual ~= #inventory.meshes then return false end
    for _, entry in ipairs(actual) do
        if expected[entry.meshId] ~= entry.count then return false end
    end
    return true
end

function Inventory.Ids(model: Model): {[string]: boolean}
    local ids = {}
    for _, part in ipairs(Inventory.Parts(model)) do
        local mid = Inventory.Id(part.MeshId)
        if mid ~= "" then ids[mid] = true end
    end
    return ids
end

local function sameFrame(a: CFrame, b: CFrame): boolean
    return (a.Position-b.Position).Magnitude < 0.04
        and a.LookVector:Dot(b.LookVector)>0.9995
        and a.UpVector:Dot(b.UpVector)>0.9995
end

function Inventory.Provenance(placed: Model, oldPublished: Model): CFrame
    -- Only a unique MeshId in both *the old immutable publication* and its
    -- placed instance can prove the historical authored transform. Old/new
    -- importer names and hierarchy are intentionally irrelevant.
    local older, placedById = {}, {}
    for _, source in ipairs({{oldPublished,older},{placed,placedById}}) do
        for _, part in ipairs(Inventory.Parts(source[1])) do
            local mid = Inventory.Id(part.MeshId)
            if mid~="" then
                source[2][mid] = source[2][mid] or {}
                table.insert(source[2][mid],part)
            end
        end
    end
    local transform: CFrame? = nil
    for mid, oldParts in pairs(older) do
        local placedParts = placedById[mid]
        if #oldParts==1 and placedParts and #placedParts==1 then
            -- MeshPart.CFrame is the geometry frame. GetPivot includes PivotOffset,
            -- which the managed-rig transaction may rebase to preserve the
            -- placed Model pivot when a new PrimaryPart is installed. Never
            -- mistake that metadata change for a changed authored transform.
            local candidate = placedParts[1].CFrame * oldParts[1].CFrame:Inverse()
            if transform and not sameFrame(transform,candidate) then
                error("historical Mesh IDs disagree on placed transform; no Place geometry modified")
            end
            transform=candidate
        end
    end
    if not transform then
        error("cannot recover authored transform from unique historical Mesh IDs; no Place geometry modified")
    end
    return transform
end

function Inventory.VerifyChildren(oldPublished: Model, children: {Instance})
    -- Validate the COMPLETE physical-part multiset, not only membership.
    -- A manually duplicated MeshPart with an existing MeshId must not be
    -- mistaken for published geometry and silently deleted by RigSwap.
    local expectedMeshes, expectedOtherParts = {}, {}
    for _, part in ipairs(oldPublished:GetDescendants()) do
        if part:IsA("MeshPart") then
            local mid = Inventory.Id(part.MeshId)
            expectedMeshes[mid] = (expectedMeshes[mid] or 0) + 1
        elseif part:IsA("BasePart") then
            expectedOtherParts[part.ClassName] = (expectedOtherParts[part.ClassName] or 0) + 1
        end
    end
    local actualMeshes, actualOtherParts = {}, {}
    for _, child in ipairs(children) do
        local parts = {}
        if child:IsA("BasePart") then table.insert(parts, child) end
        for _, descendant in ipairs(child:GetDescendants()) do
            if descendant:IsA("BasePart") then table.insert(parts, descendant) end
        end
        if #parts == 0 then error("unverified placed geometry subtree; no Place geometry modified") end
        for _, part in ipairs(parts) do
            if part:IsA("MeshPart") then
                local mid = Inventory.Id(part.MeshId)
                actualMeshes[mid] = (actualMeshes[mid] or 0) + 1
            else
                actualOtherParts[part.ClassName] = (actualOtherParts[part.ClassName] or 0) + 1
            end
        end
    end
    for mid, count in pairs(expectedMeshes) do
        if actualMeshes[mid] ~= count then
            error("placed MeshPart inventory differs from previous published Model; no Place geometry modified")
        end
    end
    for mid in pairs(actualMeshes) do
        if expectedMeshes[mid] == nil then
            error("placed MeshPart outside previous published Model inventory; no Place geometry modified")
        end
    end
    for className, count in pairs(expectedOtherParts) do
        if actualOtherParts[className] ~= count then
            error("placed physical part inventory differs from previous published Model; no Place geometry modified")
        end
    end
    for className in pairs(actualOtherParts) do
        if expectedOtherParts[className] == nil then
            error("unverified extra physical part in managed geometry; no Place geometry modified")
        end
    end
    -- The outgoing rig can also contain Bones, WrapLayers, attachments,
    -- constraints or hand-added scripts. Merely matching MeshId counts does
    -- NOT authorize destroying arbitrary children of those MeshParts. Compare
    -- the full non-texture class hierarchy of the previous immutable Model
    -- with the managed outgoing subtrees. Names are intentionally ignored:
    -- authoring may rename parts, and Mesh IDs establish provenance.
    -- SurfaceAppearance is atlas-managed. Portable Bone effects and safe
    -- Bone > Attachment > effects subtrees are cloned onto the staged rig by
    -- StudioPlacedRigBoneEffects. Ignore only complete, whitelisted subtrees:
    -- any extra Script, geometry or unknown Attachment child still blocks Sync.
    -- Other unknown descendants still fail closed.
    local function signatures(roots: {Instance}): {[string]: number}
        local result = {}
        local function visit(item: Instance, prefix: string)
            if item:IsA("SurfaceAppearance") or BoneEffects.IsPortable(item) then return end
            local path = prefix .. "/" .. item.ClassName
            result[path] = (result[path] or 0) + 1
            for _, child in ipairs(item:GetChildren()) do
                visit(child, path)
            end
        end
        for _, root in ipairs(roots) do visit(root, "") end
        return result
    end
    local oldChildren = {}
    for _, child in ipairs(oldPublished:GetChildren()) do
        if child:IsA("BasePart") or (child:IsA("Model") or child:IsA("Folder"))
            and child:FindFirstChildWhichIsA("BasePart", true) then
            table.insert(oldChildren, child)
        end
    end
    local expectedTree = signatures(oldChildren)
    local actualTree = signatures(children)
    for path, count in pairs(expectedTree) do
        if actualTree[path] ~= count then
            error("placed rig hierarchy differs from previously published Model; no Place geometry modified")
        end
    end
    for path in pairs(actualTree) do
        if expectedTree[path] == nil then
            error("unverified placed rig descendant; no Place geometry modified")
        end
    end
end

-- An untagged historic MeshPart is NEVER proof of ownership by itself.
-- Only an entire previously published Model inventory allows an explicit
-- link action. Fail closed if any ancestor/descendant has asset ownership.
local function hasForeignOwnership(model: Model, workspace: Workspace): boolean
    local cursor: Instance? = model
    while cursor and cursor ~= workspace do
        if cursor:IsA("Model") and (cursor:GetAttribute("Game1DecoAssetSlug") ~= nil
            or cursor:GetAttribute("Game1DecoInstanceId") ~= nil) then return true end
        cursor=cursor.Parent
    end
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("Model") and (item:GetAttribute("Game1DecoAssetSlug") ~= nil
            or item:GetAttribute("Game1DecoInstanceId") ~= nil) then return true end
    end
    return false
end

local function legacyCandidate(part: MeshPart, workspace: Workspace,
    versions: {any}, currentModelId: string): (Model?, string?)
    local model=part:FindFirstAncestorOfClass("Model")
    while model and model:IsDescendantOf(workspace) do
        if hasForeignOwnership(model, workspace) then return nil, nil end
        local matched: string? = nil
        local ambiguous = false
        for _, version in ipairs(versions) do
            if version.modelAssetId ~= currentModelId and Inventory.MatchesInventory(model,version) then
                if matched then ambiguous=true break end
                matched=version.modelAssetId
            end
        end
        if ambiguous then return nil,nil end
        if matched then return model,matched end
        local parent=model.Parent
        while parent and parent~=workspace and not parent:IsA("Model") do parent=parent.Parent end
        model=if parent and parent:IsA("Model") then parent else nil
    end
    return nil,nil
end

-- Every managed MeshPart is reported. Physics-only COL MeshParts have NO
-- atlas contract: their TextureID/ColorMap are irrelevant, even if old imported
-- Place geometry contains a leftover image ID.
function Inventory.Scan(workspace: Workspace, slug: string, row: any,
    versions: {string}, loader: any, cached: {any}?): any
    if #versions<1 or #versions>48 then error("invalid bounded Model history") end
    local cache = {}
    for _, entry in ipairs(cached or {}) do
        if type(entry)=="table" and type(entry.modelAssetId)=="string" and type(entry.meshes)=="table" then
            cache[entry.modelAssetId]=entry
        end
    end
    local newModelId = tostring(row.model_asset_id or "")
    local previousIds,currentIds,currentVisualIds,inventory,seenIds = {},{},{},{},{}
    for _, modelId in ipairs(versions) do
        if seenIds[modelId] then error("duplicate Model history ID") end
        seenIds[modelId]=true
        local desc=cache[modelId]
        -- M238 cache did not retain names: enrich the CURRENT publication once.
        -- Never guess visual IDs from Blender mesh names or historical IDs.
        if not desc or (modelId==newModelId and #desc.meshes>0
            and type(desc.meshes[1].visualNames)~="table") then
            local published=loader:loadForMeshInventory(modelId,slug)
            desc=Inventory.Describe(modelId,published)
            published:Destroy()
        end
        table.insert(inventory,desc)
        local bucket=if modelId==newModelId then currentIds else previousIds
        for _, entry in ipairs(desc.meshes) do
            bucket[entry.meshId]=true
            -- An unchanged published Mesh ID is still an identity. It must
            -- be discoverable without a Deco placement stamp (manual copies,
            -- renamed slugs), but a collider ID must not claim unrelated parts.
            if modelId==newModelId and type(entry.visualNames)=="table"
                and #entry.visualNames>0 then
                currentVisualIds[entry.meshId]=true
            end
        end
    end
    if not seenIds[newModelId] then error("current Model not found in published Model history") end
    for mid in pairs(currentIds) do previousIds[mid]=nil end

    local expectedMeshIds={}
    for mid in pairs(currentIds) do table.insert(expectedMeshIds,mid) end
    table.sort(expectedMeshIds)
    local roots, seenRoot, geometryRoots={}, {}, {}
    local rows, partByKey, legacyCandidates, legacySeen={}, {}, {}, {}
    local managedCount, unmatched=0,0
    local authoring=workspace:FindFirstChild("Game1Authoring")
    local camera=workspace.CurrentCamera
    local atlasId=tostring(row.texture_asset_id or "")
    for _, part in ipairs(workspace:GetDescendants()) do
        if part:IsA("MeshPart") and not Carrier.IsCarrier(part)
            and (not authoring or not part:IsDescendantOf(authoring))
            and (not camera or not part:IsDescendantOf(camera)) then
            local meshId=Inventory.Id(part.MeshId)
            local old=previousIds[meshId]==true
            -- A retained slug alias is the SAME registered asset identity.
            -- Treat its nearest stamped root as one managed placement so a
            -- two-part legacy rig is not rendered as two unrelated assets.
            local owner = Ownership.ForPart(workspace, part, slug, row.aliases)
            local currentUnlinked = owner==nil and currentVisualIds[meshId]==true
                and not MeshPhysics.IsCollider(part.Name)
                and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
            if old or owner or currentUnlinked then
                if #rows>=4096 then error("more than 4096 matching MeshParts in Workspace") end
                local key="p"..tostring(#rows+1)
                local surface=part:FindFirstChildOfClass("SurfaceAppearance")
                local textureApplicable = not MeshPhysics.IsCollider(part.Name)
                    and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
                local textureId=if textureApplicable then Inventory.Id(part.TextureID) else ""
                local colorMapId=if textureApplicable and surface then Inventory.Id(surface.ColorMap) else ""
                local textureCurrent=not textureApplicable or (textureId==atlasId
                    and (not surface or colorMapId==atlasId))
                local alphaEnabled=row.alphaEnabled==true
                local alphaCurrent=not textureApplicable or (surface~=nil and
                    surface.AlphaMode==(if alphaEnabled then Enum.AlphaMode.Transparency else Enum.AlphaMode.Opaque))
                local meshCurrent=currentIds[meshId]==true
                -- Authored skeleton layout is validated independently of MeshId:
                -- the visual Mesh ID may be unchanged across publications.
                local rigState=if owner then Carrier.Diagnose(owner,row.rigManifest,row.legacyStaticPublication) else ""
                local inspectionRequired=owner~=nil and row.needsFbxInspection==true
                local republishRequired=owner~=nil and not inspectionRequired
                    and not Carrier.IsCanonicalPublication(row.rigManifest,row.legacyStaticPublication)
                local needsCanonicalReplacement=owner~=nil and rigState~="current"
                    and not republishRequired and not inspectionRequired
                local path=part:GetFullName()
                local legacyRoot,legacyModelId=nil,nil
                if old and not owner then
                    legacyRoot,legacyModelId=legacyCandidate(part,workspace,inventory,newModelId)
                    if legacyRoot and legacySeen[legacyRoot] then legacyRoot,legacyModelId=nil,nil end
                    if legacyRoot then legacySeen[legacyRoot]=true end
                end
                -- Untagged current-version meshes inside author-created folders
                -- are independent placements, NOT one giant grouping Model.
                -- Historical whole-model candidates retain their verified root.
                local container=owner or legacyRoot or part
                local entry={key=key,name=part.Name,path=string.sub(path,1,240),
                    modelName=string.sub(container.Name,1,128),
                    modelPath=string.sub(container:GetFullName(),1,240),
                    isCollider=MeshPhysics.IsCollider(part.Name),
                    instanceId=if owner then tostring(owner:GetAttribute("Game1DecoInstanceId")) else "",
                    meshId=meshId,textureId=textureId,colorMapId=colorMapId,
                    hasSurface=textureApplicable and surface~=nil,textureApplicable=textureApplicable,managed=owner~=nil,
                    attachable=legacyRoot~=nil,historicalModelId=legacyModelId or "",
                    meshCurrent=meshCurrent,textureCurrent=textureCurrent,
                    needsMesh=false,needsTexture=not textureCurrent,needsAlpha=not alphaCurrent,
                    alphaEnabled=alphaEnabled,alphaCurrent=alphaCurrent,
                    currentUnlinked=currentUnlinked,
                    rigState=rigState,republishRequired=republishRequired,
                    needsFbxInspection=inspectionRequired,
                    needsCanonicalReplacement=needsCanonicalReplacement}
                table.insert(rows,entry)
                partByKey[key]={part=part,root=owner,row=entry,
                    selectTarget=container}
                if legacyRoot then
                    legacyCandidates[key]={root=legacyRoot,modelId=legacyModelId,
                        parent=legacyRoot.Parent,pivot=legacyRoot:GetPivot(),
                        scale=legacyRoot:GetScale(),meshCount=#Inventory.Parts(legacyRoot)}
                end
                if owner then
                    managedCount+=1
                    if not seenRoot[owner] then
                        table.insert(roots,owner)
                        seenRoot[owner]=true
                    end
                    if republishRequired or needsCanonicalReplacement or old or not meshCurrent
                        or tostring(owner:GetAttribute("Game1DecoPublishedModelAssetId") or "")~=newModelId
                        or tostring(owner:GetAttribute("Game1DecoPublishedModelSha256") or "")~=tostring(row.model_published_sha256 or "") then
                        geometryRoots[owner]=true
                    end
                else
                    unmatched+=1
                end
            end
        end
    end
    local texturePending, meshPending, alphaPending, pending=0,0,0,0
    for _ in pairs(geometryRoots) do pending+=1 end
    for _, entry in ipairs(rows) do
        if entry.managed then
            local bound=partByKey[entry.key]
            entry.needsMesh=geometryRoots[bound.root]==true
            if entry.needsMesh then meshPending+=1 end
            if entry.needsTexture then texturePending+=1 end
            if entry.needsAlpha then alphaPending+=1 end
        end
    end
    -- Find is strictly read-only and never changes Studio Selection. The user
    -- explicitly selects a single row via the separate Select in Studio phase.
    local mode=if pending>0 and (texturePending>0 or alphaPending>0) then "texture_mesh"
        elseif pending>0 then "mesh" elseif texturePending>0 then "texture"
        elseif alphaPending>0 then "alpha" else "current"
    return {inventory=inventory,expectedMeshIds=expectedMeshIds,parts=rows,
        partByKey=partByKey,legacyCandidates=legacyCandidates,
        foundMeshParts=#rows,managedMeshParts=managedCount,
        unmanagedMeshParts=unmatched,managedModels=#roots,
        texturePending=texturePending,alphaPending=alphaPending,meshPending=meshPending,geometryPending=pending,mode=mode,
        roots=roots,geometryRoots=geometryRoots,
        publishedModelId=newModelId,publishedAtlasId=atlasId}
end

return table.freeze(Inventory)

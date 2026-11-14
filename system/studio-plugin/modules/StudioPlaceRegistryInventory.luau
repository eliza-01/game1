local Carrier = require(script.Parent.StudioLocationRigCarrier)
-- M240: Registry-backed Location Assets ONLY. Scan is strictly read-only.
-- No Workspace classification by name/category; only immutable published Mesh IDs.
local History = require(script.Parent.StudioPublishedMeshHistory)
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local Published = require(script.Parent.StudioLocationPublishedGeometry)
local Visual = require(script.Parent.StudioLocationVisualAppearance)
local CarrierRig = require(script.Parent.StudioLocationRigCarrier)
local collisionModuleOk, Collision = pcall(require, script.Parent.StudioLocationCollisionParts)
local Inventory = {}

local function id(uri: any): string
    return History.Id(uri)
end

local function visual(part: MeshPart): boolean
    return not Carrier.IsCarrier(part) and not Physics.IsCollider(part.Name) and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
end

local function hasForeignOwner(obj: Instance): boolean
    local parent: Instance? = obj
    while parent and parent ~= workspace do
        -- Other domain's EXPLICIT owner is stronger than incidental shared Mesh ID.
        if parent:GetAttribute("Game1RealEstateSlug") ~= nil
            or parent:GetAttribute("Game1PlotHousePreview") == true then return true end
        parent = parent.Parent
    end
    return false
end

local function ensureVersions(catalog: any, service: any): ({any}, {any}, {string})
    local versions = {}
    local inventory = {}
    local warnings = {}
    for _, item in ipairs(catalog.items) do
        local published = {}
        for _, version in ipairs(item.models) do
            local info = version
            local incomplete=#version.meshes == 0
            for _, mesh in ipairs(version.meshes) do
                if type(mesh.visualNames)~="table" then incomplete=true end
            end
            if incomplete then
                local loaded, source=pcall(service.loader.loadForMeshInventory,service.loader,
                    version.modelAssetId,item.slug)
                if loaded then
                    local ok, described = pcall(History.Describe, version.modelAssetId, source)
                    source:Destroy()
                    if ok then
                        info=described
                    else
                        table.insert(warnings,"Не считана история Mesh ID "..item.slug.." / "..version.modelAssetId)
                    end
                else
                    table.insert(warnings,"Model ID недоступен в Studio: "..item.slug.." / "..version.modelAssetId)
                end
            end
            table.insert(published, info)
        end
        table.insert(inventory, {slug=item.slug,models=published})
        table.insert(versions, {slug=item.slug,aliases=item.aliases or {},
            atlas=item.atlasAssetId,model=item.modelAssetId,
            sha=item.publishedSha,material=item.surfaceMaterial or "default",
            appearanceMode=item.appearanceMode or "atlas", visualMaterial=item.visualMaterial or "SmoothPlastic",
            visualColor=item.visualColor or "#FFFFFF",
            alphaEnabled=item.alphaEnabled==true,models=published,
            collisionBlueprint=item.collisionBlueprint,
            collisionRevision=item.collisionBlueprintRevision or 0,
            collisionSha=item.collisionBlueprintSha256 or "",
            rigManifest=item.rigManifest,legacyStaticPublication=item.legacyStaticPublication==true,
            needsFbxInspection=item.needsFbxInspection==true})
    end
    return versions,inventory,warnings
end

local function signatures(versions: {any}): ({[string]: {any}}, {[string]: any})
    local byMesh,bySlug={},{}
    for _, entry in ipairs(versions) do
        bySlug[entry.slug]=entry
        for _, version in ipairs(entry.models) do
            for _, mesh in ipairs(version.meshes) do
                -- A physical collider's ID must not qualify other objects as decorations.
                if type(mesh.visualNames)=="table" and #mesh.visualNames>0 then
                    byMesh[mesh.meshId]=byMesh[mesh.meshId] or {}
                    local slots=byMesh[mesh.meshId]
                    local already=false
                    for _, candidate in ipairs(slots) do
                        if candidate.slug==entry.slug then already=true break end
                    end
                    if not already then table.insert(slots,entry) end
                end
            end
        end
    end
    return byMesh,bySlug
end

-- Only a Model whose WHOLE MeshPart multiset matches one historical published
-- version is an asset instance. Arbitrary hand-made grouping Models are not.
local function closestPublishedRoot(part: MeshPart, entry: any): Model?
    local candidate=part.Parent
    while candidate and candidate~=workspace do
        if candidate:IsA("Model") then
            local meshCount=0
            for _, child in ipairs(candidate:GetDescendants()) do
                if child:IsA("MeshPart") then meshCount+=1 end
            end
            if meshCount<=32 then
                for _, version in ipairs(entry.models) do
                    if History.MatchesInventory(candidate,version) then return candidate end
                end
            end
        end
        candidate=candidate.Parent
    end
    return nil
end

local function positionOf(part: MeshPart): {number}
    return {part.Position.X,part.Position.Y,part.Position.Z}
end

-- Recoverable forensic data for IDENTIFIED decorations only (no scripts or
-- unknown Workspace trees). Preserves collider/Bone ancestry and transforms.
local function hierarchy(anchor: Instance): {any}
    local objects={anchor}
    for _,child in ipairs(anchor:GetDescendants()) do
        if #objects>=512 then break end
        table.insert(objects,child)
    end
    local indices={}
    for index,obj in ipairs(objects) do indices[obj]=index end
    local result={}
    for index,obj in ipairs(objects) do
        local entry={id=index,parent=indices[obj.Parent],class=obj.ClassName,name=obj.Name}
        local attrs={}
        for key,value in pairs(obj:GetAttributes()) do
            local low=key:lower()
            if not (low:find("password",1,true) or low:find("secret",1,true)
                or low:find("token",1,true) or low:find("key",1,true)) then
                if type(value)=="string" or type(value)=="number" or type(value)=="boolean" then
                    if type(value)~="string" or #value<20000 then attrs[key]=value end
                end
            end
        end
        entry.attributes=attrs
        if obj:IsA("BasePart") then
            entry.cframe={obj.CFrame:GetComponents()}
            entry.size={obj.Size.X,obj.Size.Y,obj.Size.Z}
            entry.anchored=obj.Anchored
            entry.canCollide=obj.CanCollide
            entry.canQuery=obj.CanQuery
            entry.transparency=obj.Transparency
        end
        if obj:IsA("MeshPart") then
            entry.meshId=id(obj.MeshId)
            entry.textureId=id(obj.TextureID)
            entry.doubleSided=obj.DoubleSided
            entry.collisionFidelity=tostring(obj.CollisionFidelity)
        elseif obj:IsA("SurfaceAppearance") then
            entry.colorMap=id(obj.ColorMap)
            entry.alphaMode=tostring(obj.AlphaMode)
            entry.normalMap=id(obj.NormalMap)
            entry.roughnessMap=id(obj.RoughnessMap)
            entry.metalnessMap=id(obj.MetalnessMap)
        elseif obj:IsA("Bone") or obj:IsA("Attachment") then
            entry.cframe={obj.CFrame:GetComponents()}
        end
        table.insert(result,entry)
    end
    return result, (#anchor:GetDescendants()+1 > #objects)
end

local function state(part: MeshPart): any
    local surface=part:FindFirstChildOfClass("SurfaceAppearance")
    return {parent=part.Parent, frame=part.CFrame, size=part.Size,
        meshId=id(part.MeshId), textureId=id(part.TextureID),
        collider=Physics.IsCollider(part.Name) or part:GetAttribute("Game1DecoPhysicsOnly")==true,
        colorMap=if surface then id(surface.ColorMap) else "",
        alphaMode=if surface then surface.AlphaMode else nil,
        material=part.Material,color=part.Color,
        appearanceMode=part:GetAttribute("Game1DecoAppearanceMode"),
        visualMaterial=part:GetAttribute("Game1DecoVisualMaterial"),
        visualColor=part:GetAttribute("Game1DecoVisualColor")}
end

function Inventory.Scan(workspaceService: Workspace, catalog: any, service: any): any
    if not collisionModuleOk then
        error("Collision generator unavailable; Place inventory not modified: " .. tostring(Collision))
    end
    if catalog.domain~="location_assets" or catalog.schemaVersion~=1 then
        error("Only Location Assets may enter Place Registry")
    end
    local versions,allInventory,warnings=ensureVersions(catalog,service)
    local byMesh=signatures(versions)
    local candidates={}
    for _, descendant in ipairs(workspaceService:GetDescendants()) do
        if descendant:IsA("MeshPart") and visual(descendant) and not hasForeignOwner(descendant) then
            local owners=byMesh[id(descendant.MeshId)]
            if owners then
                table.insert(candidates,{part=descendant,owners=owners})
            end
        end
    end
    table.sort(candidates,function(a,b)
        if a.part:GetFullName()~=b.part:GetFullName() then
            return a.part:GetFullName()<b.part:GetFullName() end
        local ax, bx = a.part.Position,b.part.Position
        if ax.X~=bx.X then return ax.X<bx.X end
        if ax.Y~=bx.Y then return ax.Y<bx.Y end
        return ax.Z<bx.Z
    end)
    if #candidates>4096 then error("Place contains >4096 identifiable Location MeshParts; run a scoped audit") end
    local rows,refs,duplicateGroups={},{},{}
    local consumed={}
    for _,candidate in ipairs(candidates) do
        local part=candidate.part
        if consumed[part] then continue end
        local eligible=#candidate.owners==1
        local entry=candidate.owners[1]
        local root=if eligible then closestPublishedRoot(part,entry) else nil
        local visualParts={part}
        if root then
            visualParts={}
            for _, child in ipairs(root:GetDescendants()) do
                if child:IsA("MeshPart") and visual(child) then
                    table.insert(visualParts,child)
                end
            end
        end
        for _,visualPart in ipairs(visualParts) do consumed[visualPart]=true end
        local placement: Instance = root or part
        local original = state(part)
        local oldId,oldAmbiguous="",true
        if eligible then oldId,oldAmbiguous=Published.ResolveOldVersion(entry,root,id(part.MeshId)) end
        local issues={}
        local function warn(code: string) table.insert(issues,code) end
        local needsMesh=eligible and not Published.VisualCurrent(entry,id(part.MeshId))
        -- The visible MeshId may be unchanged across publications. Check the
        -- entire published shape (including COL), not only that one MeshId.
        local needsRig=eligible and root~=nil and not Published.CurrentShape(entry,root)
        local needsTexture=false
        if eligible then
            for _, visualPart in ipairs(visualParts) do
                if not Visual.IsCurrent(visualPart, {
                    appearanceMode=entry.appearanceMode, visualMaterial=entry.visualMaterial,
                    visualColor=entry.visualColor, texture_asset_id=entry.atlas,
                    alphaEnabled=entry.alphaEnabled,
                }) then
                    needsTexture=true
                    break
                end
            end
        end
        local needsAlpha=false
        if eligible and entry.appearanceMode~="material" then
            for _, visualPart in ipairs(visualParts) do
                local appearance=visualPart:FindFirstChildOfClass("SurfaceAppearance")
                local mode=if entry.alphaEnabled then Enum.AlphaMode.Transparency else Enum.AlphaMode.Opaque
                if not appearance or appearance.AlphaMode~=mode then
                    needsAlpha=true
                    break
                end
            end
        end
        local needsMaterial=false
        if eligible then
            for _, candidatePart in ipairs(root and root:GetDescendants() or {part}) do
                if candidatePart:IsA("MeshPart") and visual(candidatePart) then
                    local prior = candidatePart:GetAttribute("Game1LocationSurfaceMaterial")
                    if prior ~= entry.material and (entry.material ~= "default"
                        or (prior ~= nil and prior ~= "default")) then
                        needsMaterial=true
                        break
                    end
                end
            end
        end
        local structuralState = if root then CarrierRig.Diagnose(root,if eligible then entry.rigManifest else nil,
            eligible and entry.legacyStaticPublication)
            else "repair_required"
        local hasImporterRoot = structuralState == "legacy_import_root"
        -- A legacy imported RootPart is a defect of the FBX publication.
        -- NEVER advertise an in-Place skeleton Repair for this state.
        local needsInspection = eligible and entry.needsFbxInspection==true
        local requiresRepublish = eligible and not needsInspection
            and not CarrierRig.IsCanonicalPublication(entry.rigManifest,entry.legacyStaticPublication)
        local needsCollision = eligible and root ~= nil and entry.collisionRevision > 0
            and not Collision.Current(root,entry.collisionBlueprint,entry.collisionRevision,entry.collisionSha)
        local needsReplacement = eligible and structuralState ~= "current"
            and not requiresRepublish and not needsInspection
        if eligible and structuralState == "legacy_import_root" then
            if requiresRepublish then
                warn("Импортный RootPart — требуется перепубликация FBX; атлас не меняется")
            else
                warn("Импортный RootPart в старом размещении — каноническая публикация уже есть; требуется обновление экземпляра, не Repair")
            end
        elseif needsInspection then
            warn("Сначала Analyze saved FBX: отсутствует проверка наличия Bone; перепубликация пока не требуется")
        elseif eligible and requiresRepublish then
            warn("Структура FBX неканоническая ("..structuralState.."); требуется перепубликация FBX")
        elseif eligible and structuralState ~= "current" then
            if oldId~="" then
                warn("Историческая структура подтверждена публикацией "..oldId
                    .."; Sync заменит дочерний rig канонической Model: "..structuralState)
            else
                warn("Структура размещения не соответствует канонической публикации: "..structuralState)
            end
        end
        if not eligible then warn("Один Mesh ID встречается у нескольких Location Assets") end
        if not root then warn("Нет отдельной Model для этого экземпляра") end
        if needsRig and not needsMesh then warn("Новая версия модели отличается по составу MeshPart, хотя визуальный Mesh ID совпадает") end
        if needsMaterial then warn("Звуковой материал требует Sync: "..entry.material) end
        if needsCollision then warn("Collision Blueprint требует Sync: ревизия "..tostring(entry.collisionRevision)) end
        if needsTexture and entry.appearanceMode=="material" then
            warn("Roblox Material / Color требует Sync")
        end
        if needsAlpha then warn("AlphaMode требует Sync") end
        if eligible and oldAmbiguous then
            oldId=""
            warn("Один Mesh ID встречается в нескольких версиях; геометрия требует ручной проверки")
        end
        local meshNameMismatch=eligible and not entry.rigManifest and not entry.legacyStaticPublication
            and #visualParts==1 and visualParts[1].Name~=entry.slug
        if meshNameMismatch then warn("Имя MeshPart не соответствует slug ассета") end
        local badName=false
        if eligible and root and root.Name~=entry.slug.."__"..tostring(root:GetAttribute("Game1DecoInstanceId") or ""):sub(1,8) then
            badName=true
            warn("Имя модели не соответствует стандарту")
        end
        local assigned=tostring(placement:GetAttribute("Game1DecoInstanceId") or "")
        local claimed=if root then tostring(root:GetAttribute("Game1DecoAssetSlug") or "") else ""
        local oldClaim=false
        if eligible and claimed~="" then
            for _,alias in ipairs(entry.aliases or {}) do
                if claimed==alias then oldClaim=true break end
            end
        end
        local foreignClaim=eligible and claimed~="" and claimed~=entry.slug and not oldClaim
        local provenForeignClaim=false
        if foreignClaim and root then
            -- A copied/slightly renamed model can carry someone else's old
            -- Game1DecoAssetSlug. That attribute is NOT proof of ownership.
            -- Only the complete published MeshId inventory of the claimed
            -- asset may outweigh the unambiguous historical MeshId we found.
            for _,other in ipairs(versions) do
                local claimsOther=other.slug==claimed
                for _,alias in ipairs(other.aliases or {}) do
                    if alias==claimed then claimsOther=true break end
                end
                if claimsOther then
                    for _,publication in ipairs(other.models) do
                        if History.MatchesInventory(root,publication) then
                            provenForeignClaim=true
                            break
                        end
                    end
                    break
                end
            end
        end
        if oldClaim then warn("Исторический slug: "..claimed.." → "..entry.slug
            .."; Sync мигрирует идентичность вместе с опубликованным rig") end
        if foreignClaim and provenForeignClaim then
            warn("Конфликт двух подтверждённых Location Assets; требуется ручная проверка")
        elseif foreignClaim then
            warn("Устаревшая метка slug: "..claimed.." → "..entry.slug.." (по Mesh ID); Repair исправит")
        end
        if assigned=="" then warn("Нет Placement ID") else
            duplicateGroups[assigned]=duplicateGroups[assigned] or {}
            table.insert(duplicateGroups[assigned],#rows+1)
        end
        local fullHierarchy,truncated=hierarchy(placement)
        if truncated then
            warn("Снимок иерархии превышает 512 объектов; неполная ревизия")
            table.insert(warnings, "Слишком большая иерархия: "..placement:GetFullName())
        end
        local key="p"..tostring(#rows+1)
        local visualStates={}
        for _,child in ipairs(visualParts) do visualStates[child]=state(child) end
        local meshStates={}
        if root then
            for _,child in ipairs(root:GetDescendants()) do
                if child:IsA("MeshPart") then meshStates[child]=state(child) end
            end
        else
            meshStates[part]=state(part)
        end
        local row={key=key,slug=if eligible then entry.slug else candidate.owners[1].slug,
            name=placement.Name,path=placement:GetFullName(),placementId=assigned,
            modelAssetId=if eligible then oldId else "",meshId=original.meshId,
            textureId=original.textureId,expectedMeshId=if eligible then entry.model else "",
            expectedTextureId=if eligible then entry.atlas else "",
            needsMesh=needsMesh,needsRig=needsRig,needsTexture=needsTexture,needsMaterial=needsMaterial,needsAlpha=needsAlpha,
            needsCollision=needsCollision,collisionRevision=entry.collisionRevision,needsStructure=structuralState ~= "current" or not root or badName or meshNameMismatch or assigned==""
                or (root and root:GetAttribute("Game1DecoAssetSlug")~=entry.slug),

            duplicateId=false,ambiguous=not eligible or provenForeignClaim,
            -- Repair remains metadata-only. A verified old publication is
            -- migrated by Sync through the shared whole-child-rig swap.
            canRepair=eligible and structuralState == "current" and root~=nil
                and not needsMesh and not needsRig,
            requiresRepublish=requiresRepublish == true,
            needsFbxInspection=needsInspection == true,
            needsCanonicalReplacement=needsReplacement == true,
            hasModel=root~=nil,structuralState=structuralState,canSync=eligible and not foreignClaim
                and root~=nil and assigned~="" and (claimed==entry.slug or oldClaim)
                and not requiresRepublish and not needsInspection
                and (structuralState=="current" or (needsReplacement and oldId~=""))
                and (not needsMesh and not needsRig or oldId~=""),
            status=if not eligible then "ambiguous" elseif needsMesh or needsRig or needsTexture or needsMaterial or needsAlpha or needsCollision
                or structuralState ~= "current" or not root or badName or meshNameMismatch or assigned==""
                or oldClaim or foreignClaim
                then "pending" else "current",
            issues=issues,hierarchy=fullHierarchy,transform={cframe={part.CFrame:GetComponents()},
                size={part.Size.X,part.Size.Y,part.Size.Z},position=positionOf(part),
                anchored=part.Anchored,canCollide=part.CanCollide},
        }
        table.insert(rows,row)
        refs[key]={part=part,root=root,placement=placement,visuals=visualParts,
            visualStates=visualStates,meshStates=meshStates,
            rootParent=if root then root.Parent else nil,
            rootPivot=if root then root:GetPivot() else nil,
            rootPrimary=if root then root.PrimaryPart else nil,
            row=row,entry=if eligible then entry else nil,structuralState=structuralState,
            oldVersion=oldId,hasImporterRoot=hasImporterRoot,
            collisionCurrent=if root then Collision.Current(root,entry.collisionBlueprint,entry.collisionRevision,entry.collisionSha) else true,
            currentVisual=eligible and Published.VisualCurrent(entry,id(part.MeshId))}
    end
    for _,indexes in pairs(duplicateGroups) do
        if #indexes>1 then
            for _,idx in ipairs(indexes) do
                rows[idx].duplicateId=true
                rows[idx].needsStructure=true
                rows[idx].canSync=false
                table.insert(rows[idx].issues,"Повторяющийся Placement ID")
            end
        end
    end
    return {placements=rows,refs=refs,inventory=allInventory,
        placeId=workspaceService.Parent.PlaceId,warnings=warnings}
end

function Inventory.Validate(ref: any): boolean
    if not collisionModuleOk then return false end
    if not ref or ref.part.Parent==nil or ref.placement.Parent==nil then return false end
    if ref.root then
        if ref.root.Parent~=ref.rootParent or ref.root.PrimaryPart~=ref.rootPrimary
            or ref.root:GetPivot()~=ref.rootPivot then return false end
        if Collision.Current(ref.root,ref.entry.collisionBlueprint,ref.entry.collisionRevision,
            ref.entry.collisionSha) ~= ref.collisionCurrent then return false end
        local seen=0
        for _,child in ipairs(ref.root:GetDescendants()) do
            if child:IsA("MeshPart") then
                if not ref.meshStates[child] then return false end
                seen+=1
            end
        end
        local expected=0
        for _ in pairs(ref.meshStates) do expected+=1 end
        if seen~=expected then return false end
    end
    for part,old in pairs(ref.meshStates) do
        if part.Parent~=old.parent or part.CFrame~=old.frame or part.Size~=old.size
            or id(part.MeshId)~=old.meshId or id(part.TextureID)~=old.textureId
            or (Physics.IsCollider(part.Name) or part:GetAttribute("Game1DecoPhysicsOnly")==true)~=old.collider
            or part.Material~=old.material or part.Color~=old.color
            or part:GetAttribute("Game1DecoAppearanceMode")~=old.appearanceMode
            or part:GetAttribute("Game1DecoVisualMaterial")~=old.visualMaterial
            or part:GetAttribute("Game1DecoVisualColor")~=old.visualColor
            then return false end
        local surface=part:FindFirstChildOfClass("SurfaceAppearance")
        if (if surface then id(surface.ColorMap) else "")~=old.colorMap
            or (if surface then surface.AlphaMode else nil)~=old.alphaMode then return false end
    end
    return true
end

return Inventory

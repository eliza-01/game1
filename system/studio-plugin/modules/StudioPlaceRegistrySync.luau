local Carrier = require(script.Parent.StudioLocationRigCarrier)
-- Explicit Place Registry sync. Uses THE SAME StudioManagedRigSwap as Real Estate.
-- A manually grouped Model is never the swap target; each verified placement
-- is a separate Model. No general ApplyMesh or MeshId writes.
local RigSwap=require(script.Parent.StudioManagedRigSwap)
local History=require(script.Parent.StudioPublishedMeshHistory)
local BoneEffects = require(script.Parent.StudioPlacedRigBoneEffects)
local Texture=require(script.Parent.StudioTextureAppearance)
local Visual=require(script.Parent.StudioLocationVisualAppearance)
local PainterIntegrity=require(script.Parent.StudioLocationPainterIntegrity)
local Physics=require(script.Parent.StudioMeshPhysicsCore)
local Geometry=require(script.Parent.StudioLocationPlacedGeometry)
local PlacementHistory=require(script.Parent.StudioLocationPlacementHistory)
local collisionModuleOk, Collision = pcall(require, script.Parent.StudioLocationCollisionParts)
local Sync={}

local function visuals(root: Instance): {MeshPart}
    local out={}
    for _,child in ipairs(root:GetDescendants()) do
        if child:IsA("MeshPart") and not Carrier.IsCarrier(child) and not Physics.IsCollider(child.Name)
            and child:GetAttribute("Game1DecoPhysicsOnly")~=true then table.insert(out,child) end
    end
    return out
end

local function rigChildren(root: Model): {Instance}
    local result={}
    for _,child in ipairs(root:GetChildren()) do
        if Collision.IsOwned(child) then continue end
        if child:IsA("BasePart") or ((child:IsA("Model") or child:IsA("Folder"))
            and child:FindFirstChildWhichIsA("BasePart",true)) then
            table.insert(result,child)
        end
    end
    return result
end

local function stageRig(ref: any, ctx: any): any
    local root=ref.root
    if not root or root.Parent==nil then error("Repair this placement first") end
    if ref.oldVersion=="" then error("historical publication not unique") end
    local publishedRow={slug=ref.entry.slug,status="PUBLISHED",
        model_asset_id=ref.entry.model,texture_asset_id=ref.entry.atlas,
        surfaceMaterial=ref.entry.material, appearanceMode=ref.entry.appearanceMode,
        visualMaterial=ref.entry.visualMaterial, visualColor=ref.entry.visualColor,
        alphaEnabled=ref.entry.alphaEnabled,meshOptions=ref.entry.meshOptions,
        rigManifest=ref.entry.rigManifest}
    local stage=ctx.loader:loadPublished(publishedRow)
    local previous=ctx.loader:loadForMeshInventory(ref.oldVersion,ref.entry.slug)
    local good,result=pcall(function()
        local oldParts=rigChildren(root)
        History.VerifyChildren(previous,oldParts)
        if #oldParts==0 then error("no managed geometry children") end
        local anchor=Geometry.Align(stage,previous,root)
        BoneEffects.CopyToIncoming(oldParts,rigChildren(stage))
        return RigSwap.Prepare(root,oldParts,rigChildren(stage),{preferredPrimary=anchor})
    end)
    previous:Destroy()
    if not good then stage:Destroy();error(tostring(result)) end
    return {swap=result,stage=stage,ref=ref,
        priorId=root:GetAttribute("Game1DecoPublishedModelAssetId"),
        priorSha=root:GetAttribute("Game1DecoPublishedModelSha256"),
        priorRegistry=root:GetAttribute("Game1DecoRegistryModelAssetId"),
        priorSlug=root:GetAttribute("Game1DecoAssetSlug"),
        priorName=root.Name,
        priorHistory=root:GetAttribute("Game1DecoSyncHistory")}
end

function Sync.Apply(refs: {any}, ctx: any): any
    if not collisionModuleOk then
        error("Collision generator unavailable; Place unchanged: " .. tostring(Collision))
    end
    local plan,blocked,stages={},{},{}
    -- Prepare EVERY geometry transaction before touching any placed object.
    for _,ref in ipairs(refs) do
        if ref.external then
            if ref.row.canSync then
                local changes={}
                for _,part in ipairs(ref.visuals) do table.insert(changes,Visual.Capture(part)) end
                local names,allowed={},{ }
                for _,part in ipairs(ref.visuals) do
                    names[part.Name]=true
                    allowed[part]=true
                end
                local physics=Physics.CaptureLocationModel(ref.root,names)
                table.insert(plan,{ref=ref,external=true,appearance=changes,
                    physics=physics,physicsNames=names,physicsAllowed=allowed})
            else
                table.insert(blocked,ref.row.key..": нет изменённых визуальных настроек")
            end
            continue
        end
        if not ref.row.canSync or not ref.root then
            table.insert(blocked,ref.row.key..": требуется Repair или проверка происхождения")
            continue
        end
        if ref.row.needsMesh or ref.row.needsRig then
            local ok,stage=pcall(stageRig,ref,ctx)
            if ok then
                table.insert(plan,stage)
                table.insert(stages,stage)
            else
                table.insert(blocked,ref.row.key..": "..tostring(stage):sub(1,180))
            end
        elseif ref.row.needsTexture or ref.row.needsMaterial or ref.row.needsAlpha or ref.row.needsCollision then
            local changes={}
            for _,part in ipairs(ref.visuals) do
                table.insert(changes,Visual.Capture(part))
            end
            table.insert(plan,{ref=ref,appearance=changes,
                priorSurface=Physics.CaptureLocationSurfaceMaterial(ref.root),
                priorHistory=ref.root:GetAttribute("Game1DecoSyncHistory")})
        end
    end
    -- Stage ALL collision changes before the first Place mutation. Geometry
    -- replacements and collision recipes share one explicit Undo transaction.
    for _, item in ipairs(plan) do
        local ref = item.ref
        if ref.row.needsCollision then
            local ok, transaction
            if ref.entry.collisionRevision == 0 then
                ok, transaction=pcall(Collision.PrepareClear,ref.root)
            else
                ok, transaction=pcall(Collision.Prepare, ref.root,
                    ref.entry.collisionBlueprint,ref.entry.collisionRevision,ref.entry.collisionSha,
                    item.stage)
            end
            if not ok then
                for _, previous in ipairs(plan) do
                    if previous.collision then Collision.Rollback(previous.collision) end
                end
                for _, stage in ipairs(stages) do stage.stage:Destroy() end
                error("Collision Sync staging failed; Place unchanged: " .. tostring(transaction))
            end
            item.collision = transaction
        end
    end
    if #plan==0 then return {changed=0,skipped=blocked,
        note=if #blocked>0 then "Sync не изменил Place: проверьте причины пропуска"
            else "Нет устаревших ресурсов для Sync"} end
    local recording=ctx.history:TryBeginRecording(ctx.recordingName,"Sync Location Place Registry")
    if not recording then
        for _,item in ipairs(stages) do item.stage:Destroy() end
        for _,item in ipairs(plan) do
            if item.collision then Collision.Rollback(item.collision) end
        end
        error("Studio Undo unavailable; no Place geometry modified")
    end
    local committed={}
    local changes=0
    local ok,problem=pcall(function()
        for _,item in ipairs(plan) do
            local ref=item.ref
            local root=ref.root
            -- Add to rollback ledger BEFORE the first potentially partial write.
            table.insert(committed,item)
            if item.external then
                -- LandscapePainter owns the hierarchy and tether. The common
                -- Location Asset policy owns only visual appearance, visual
                -- MeshPart physics and managed Collision Blueprint Parts.
                local row={appearanceMode=ref.entry.appearanceMode,
                    visualMaterial=ref.entry.visualMaterial,visualColor=ref.entry.visualColor,
                    texture_asset_id=ref.entry.atlas,alphaEnabled=ref.entry.alphaEnabled,
                    meshOptions=ref.entry.meshOptions}
                PainterIntegrity.AssertUnchanged(ref.integrity)
                for _,snapshot in ipairs(item.appearance) do
                    Visual.Apply(snapshot.mesh,row)
                    Visual.AssertCurrent(snapshot.mesh,row)
                end
                if ref.row.needsPhysics then
                    Physics.ApplyLocationModel(root,item.physicsNames,ref.entry.meshOptions)
                    for _,visual in ipairs(ref.visuals) do
                        local raw=if type(ref.entry.meshOptions)=="table" then
                            ref.entry.meshOptions[visual.Name] else nil
                        local noCollide=type(raw)=="table" and raw.noCollide==true
                        if visual.CanCollide==noCollide or visual.CanQuery==noCollide
                            or visual.CanTouch then
                            error("LandscapePainter visual physics not applied: "..visual.Name)
                        end
                    end
                end
                -- Clear stale DecoManager ownership only after the Painter
                -- inventory, rig, stem/tether/sway and appearance are verified.
                -- Do not create a new Deco placement or modify the authored rig.
                if ref.row.needsOwnerCleanup then
                    root:SetAttribute("Game1DecoInstanceId",nil)
                    root:SetAttribute("Game1DecoAssetSlug",nil)
                end
                -- Includes arbitrary authored Light/Fire/Attachment/Bone descendants.
                PainterIntegrity.AssertUnchanged(ref.integrity,
                    if ref.row.needsPhysics then item.physicsAllowed else nil)
            elseif item.swap then
                RigSwap.Commit(item.swap)
                root:SetAttribute("Game1DecoAssetSlug",ref.entry.slug)
                local instanceId=tostring(root:GetAttribute("Game1DecoInstanceId") or "")
                if instanceId~="" then root.Name=ref.entry.slug.."__"..instanceId:sub(1,8) end
                root:SetAttribute("Game1DecoPublishedModelAssetId",ref.entry.model)
                root:SetAttribute("Game1DecoRegistryModelAssetId",ref.entry.model)
                root:SetAttribute("Game1DecoPublishedModelSha256",ref.entry.sha)
            else
                if ref.row.needsTexture or ref.row.needsAlpha then
                    local row={appearanceMode=ref.entry.appearanceMode,
                        visualMaterial=ref.entry.visualMaterial,visualColor=ref.entry.visualColor,
                        texture_asset_id=ref.entry.atlas,alphaEnabled=ref.entry.alphaEnabled,
                        meshOptions=ref.entry.meshOptions}
                    for _,change in ipairs(item.appearance) do
                        if ref.row.needsTexture then
                            Visual.Apply(change.mesh,row)
                        else
                            local setting=Visual.Settings(change.mesh,row)
                            if setting.appearanceMode=="material" then
                                Visual.Apply(change.mesh,row)
                            else
                                Texture.ApplyAlpha(change.mesh,setting.alphaEnabled==true,
                                    "rbxassetid://"..tostring(setting.texture_asset_id or ""))
                            end
                        end
                        Visual.AssertCurrent(change.mesh,row)
                    end
                end
            end
            if item.collision then Collision.Commit(item.collision) end
            if item.external then
                PainterIntegrity.AssertUnchanged(ref.integrity,
                    if ref.row.needsPhysics then item.physicsAllowed else nil)
            end
            if ref.row.needsMaterial then
                Physics.ApplyLocationSurfaceMaterial(root,ref.entry.material,nil)
            end
            local events={}
            if item.swap then
                table.insert(events,{kind="model",oldId=ref.oldVersion,newId=ref.entry.model,count=1})
            end
            if ref.row.needsTexture then
                table.insert(events,{kind=if ref.entry.appearanceMode=="material" then "appearance" else "atlas",
                    oldId=ref.row.textureId,
                    newId=if ref.entry.appearanceMode=="material" then ref.entry.visualMaterial..ref.entry.visualColor
                        else ref.entry.atlas,count=#ref.visuals})
            end
            if ref.row.needsMaterial then
                local previousMaterial="published geometry"
                if item.priorSurface then
                    for _,before in ipairs(item.priorSurface) do
                        if before.part==ref.part then
                            previousMaterial=tostring(before.key or "default")
                            break
                        end
                    end
                end
                table.insert(events,{kind="material",oldId=previousMaterial,
                    newId=ref.entry.material,count=#ref.visuals})
            end
            if ref.row.needsCollision then
                table.insert(events,{kind="collision",oldId=tostring(item.collision.oldRevision or 0),
                    newId=tostring(ref.entry.collisionRevision),count=#item.collision.stage})
            end
            if ref.row.needsAlpha then
                table.insert(events,{kind="alpha",oldId="previous",newId=if ref.entry.alphaEnabled then "Transparency" else "Opaque",count=#ref.visuals})
            end
            if not item.external then
                PlacementHistory.Append(root,ctx.http,ref.entry.slug,events)
            end
            changes+=1
        end
    end)
    if not ok then
        for i=#committed,1,-1 do
            local item=committed[i]
            pcall(function()
                if item.external then
                    item.ref.root:SetAttribute("Game1DecoInstanceId",item.ref.priorDecoInstanceId)
                    item.ref.root:SetAttribute("Game1DecoAssetSlug",item.ref.priorDecoSlug)
                    for _,change in ipairs(item.appearance) do Visual.Restore(change) end
                    if item.physics then Physics.RestoreLocationModel(item.physics) end
                elseif item.swap then
                    RigSwap.Rollback(item.swap)
                    item.ref.root:SetAttribute("Game1DecoPublishedModelAssetId",item.priorId)
                    item.ref.root:SetAttribute("Game1DecoPublishedModelSha256",item.priorSha)
                    item.ref.root:SetAttribute("Game1DecoRegistryModelAssetId",item.priorRegistry)
                    item.ref.root:SetAttribute("Game1DecoAssetSlug",item.priorSlug)
                    item.ref.root.Name=item.priorName
                else
                    for _,change in ipairs(item.appearance) do
                        Visual.Restore(change)
                    end
                    if item.priorSurface then
                        Physics.RestoreLocationSurfaceMaterial(item.priorSurface)
                    end
                end
                if item.collision then Collision.Rollback(item.collision) end
                if not item.external then
                    item.ref.root:SetAttribute("Game1DecoSyncHistory",item.priorHistory)
                end
            end)
        end
        for _,item in ipairs(stages) do item.stage:Destroy() end
        for _,item in ipairs(plan) do
            if item.collision and not item.collision.committed then Collision.Rollback(item.collision) end
        end
        ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Cancel)
        error("Place Sync rolled back: "..tostring(problem))
    end
    -- No old geometry is destroyed before all transactions and their audit
    -- attributes have committed successfully. This is the point of no return.
    for _,item in ipairs(committed) do
        if item.swap then RigSwap.Finalize(item.swap) end
        if item.collision then Collision.Finalize(item.collision) end
    end
    for _,item in ipairs(stages) do item.stage:Destroy() end
    ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Commit)
    return {changed=changes,skipped=blocked,undo=true,
        note="Place Sync выполнен; выполните Scan для новой ревизии"}
end

return Sync

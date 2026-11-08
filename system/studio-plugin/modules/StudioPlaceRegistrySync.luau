local Carrier = require(script.Parent.StudioLocationRigCarrier)
-- Explicit Place Registry sync. Uses THE SAME StudioManagedRigSwap as Real Estate.
-- A manually grouped Model is never the swap target; each verified placement
-- is a separate Model. No general ApplyMesh or MeshId writes.
local RigSwap=require(script.Parent.StudioManagedRigSwap)
local History=require(script.Parent.StudioPublishedMeshHistory)
local Texture=require(script.Parent.StudioTextureAppearance)
local Physics=require(script.Parent.StudioMeshPhysicsCore)
local Geometry=require(script.Parent.StudioLocationPlacedGeometry)
local PlacementHistory=require(script.Parent.StudioLocationPlacementHistory)
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
        surfaceMaterial=ref.entry.material,robloxMaterial=ref.entry.physicalMaterial,alphaEnabled=ref.entry.alphaEnabled,rigManifest=ref.entry.rigManifest}
    local stage=ctx.loader:loadPublished(publishedRow)
    local previous=ctx.loader:loadForMeshInventory(ref.oldVersion,ref.entry.slug)
    local good,result=pcall(function()
        local oldParts=rigChildren(root)
        History.VerifyChildren(previous,oldParts)
        if #oldParts==0 then error("no managed geometry children") end
        local anchor=Geometry.Align(stage,previous,root)
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
    local plan,blocked,stages={},{},{}
    -- Prepare EVERY geometry transaction before touching any placed object.
    for _,ref in ipairs(refs) do
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
        elseif ref.row.needsTexture or ref.row.needsMaterial or ref.row.needsAlpha then
            local changes={}
            for _,part in ipairs(ref.visuals) do
                table.insert(changes,Texture.Capture(part))
            end
            table.insert(plan,{ref=ref,appearance=changes,
                priorSurface=Physics.CaptureLocationSurfaceMaterial(ref.root),
                priorHistory=ref.root:GetAttribute("Game1DecoSyncHistory")})
        end
    end
    if #plan==0 then return {changed=0,skipped=blocked,
        note=if #blocked>0 then "Sync не изменил Place: проверьте причины пропуска"
            else "Нет устаревших ресурсов для Sync"} end
    local recording=ctx.history:TryBeginRecording(ctx.recordingName,"Sync Location Place Registry")
    if not recording then
        for _,item in ipairs(stages) do item.stage:Destroy() end
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
            if item.swap then
                RigSwap.Commit(item.swap)
                root:SetAttribute("Game1DecoAssetSlug",ref.entry.slug)
                local instanceId=tostring(root:GetAttribute("Game1DecoInstanceId") or "")
                if instanceId~="" then root.Name=ref.entry.slug.."__"..instanceId:sub(1,8) end
                root:SetAttribute("Game1DecoPublishedModelAssetId",ref.entry.model)
                root:SetAttribute("Game1DecoRegistryModelAssetId",ref.entry.model)
                root:SetAttribute("Game1DecoPublishedModelSha256",ref.entry.sha)
            else
                if ref.row.needsTexture or ref.row.needsAlpha then
                    local uri="rbxassetid://"..ref.entry.atlas
                    for _,change in ipairs(item.appearance) do
                        if ref.row.needsTexture then
                            Texture.ApplyLocation(change.mesh,uri,ref.entry.alphaEnabled)
                        else
                            Texture.ApplyAlpha(change.mesh,ref.entry.alphaEnabled,uri)
                        end
                    end
                end
            end
            if ref.row.needsMaterial then
                Physics.ApplyLocationSurfaceMaterial(root,ref.entry.material,ref.entry.physicalMaterial)
            end
            local events={}
            if item.swap then
                table.insert(events,{kind="model",oldId=ref.oldVersion,newId=ref.entry.model,count=1})
            end
            if ref.row.needsTexture then
                table.insert(events,{kind="atlas",oldId=ref.row.textureId,
                    newId=ref.entry.atlas,count=#ref.visuals})
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
            if ref.row.needsAlpha then
                table.insert(events,{kind="alpha",oldId="previous",newId=if ref.entry.alphaEnabled then "Transparency" else "Opaque",count=#ref.visuals})
            end
            PlacementHistory.Append(root,ctx.http,ref.entry.slug,events)
            changes+=1
        end
    end)
    if not ok then
        for i=#committed,1,-1 do
            local item=committed[i]
            pcall(function()
                if item.swap then
                    RigSwap.Rollback(item.swap)
                    item.ref.root:SetAttribute("Game1DecoPublishedModelAssetId",item.priorId)
                    item.ref.root:SetAttribute("Game1DecoPublishedModelSha256",item.priorSha)
                    item.ref.root:SetAttribute("Game1DecoRegistryModelAssetId",item.priorRegistry)
                    item.ref.root:SetAttribute("Game1DecoAssetSlug",item.priorSlug)
                    item.ref.root.Name=item.priorName
                else
                    for _,change in ipairs(item.appearance) do
                        Texture.Restore(change)
                    end
                    if item.priorSurface then
                        Physics.RestoreLocationSurfaceMaterial(item.priorSurface)
                    end
                end
                item.ref.root:SetAttribute("Game1DecoSyncHistory",item.priorHistory)
            end)
        end
        for _,item in ipairs(stages) do item.stage:Destroy() end
        ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Cancel)
        error("Place Sync rolled back: "..tostring(problem))
    end
    -- No old geometry is destroyed before all transactions and their audit
    -- attributes have committed successfully. This is the point of no return.
    for _,item in ipairs(committed) do
        if item.swap then RigSwap.Finalize(item.swap) end
    end
    for _,item in ipairs(stages) do item.stage:Destroy() end
    ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Commit)
    return {changed=changes,skipped=blocked,undo=true,
        note="Place Sync выполнен; выполните Scan для новой ревизии"}
end

return Sync

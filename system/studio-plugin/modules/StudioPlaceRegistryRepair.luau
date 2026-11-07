-- Studio-only explicit, undo-recorded migration of Location placements.
-- Hand-made grouping containers are retained; only matching visual parts get wrappers.
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local MeshNames = require(script.Parent.StudioLocationMeshNames)
local Published = require(script.Parent.StudioLocationPublishedGeometry)
local History = require(script.Parent.StudioPublishedMeshHistory)
local PlacementHistory = require(script.Parent.StudioLocationPlacementHistory)
local Repair = {}

local function safeForWrapper(part: MeshPart): boolean
    -- Parenting parts with external attachments/joints changes their authoring
    -- lifecycle; do not guess which other system owns such connections.
    -- PrimaryPart is allowed: after wrapping, the MeshPart is still a
    -- descendant of its grouping Model. Preserve and verify that anchor in
    -- the wrapping transaction instead of silently skipping the placement.
    for _, child in ipairs(part:GetDescendants()) do
        if child:IsA("JointInstance") or child:IsA("Constraint") then return false end
    end
    return true
end

local function assignedId(http: any): string
    return http:GenerateGUID(false)
end

local function rename(root: Model, slug: string, placementId: string)
    root.Name=slug.."__"..placementId:sub(1,8)
end

local function restoreCol(ref: any, template: any)
    if not ref.root or not ref.needsCol then return nil end
    -- A new publication can add COL without changing the visual MeshId.
    -- Repair that additive difference without swapping the old visible rig.
    if not ref.currentVisual or #ref.visuals ~= 1 then
        error("COL требует полного обновления визуальной геометрии; отдельный Repair невозможен")
    end
    local sourceVisual: MeshPart?=nil
    local sourceCol: MeshPart?=nil
    for _, child in ipairs(template:GetDescendants()) do
        if child:IsA("MeshPart") then
            if Physics.IsCollider(child.Name) or child:GetAttribute("Game1DecoPhysicsOnly")==true then
                if sourceCol then error("more than one collider; manual repair required") end
                sourceCol=child
            else
                if sourceVisual then error("multi-part rig requires manual collider repair") end
                sourceVisual=child
            end
        end
    end
    if not sourceVisual or not sourceCol then
        error("нет однозначной опубликованной пары visual + COL")
    end
    if History.Id(sourceVisual.MeshId) ~= History.Id(ref.part.MeshId) then
        error("визуальный Mesh ID отличается: добавление COL без полного Sync запрещено")
    end
    if not ref.part.Anchored then
        error("незакреплённый visual MeshPart: нельзя добавить отдельный COL без проверки соединений")
    end
    -- Bones and visual-only effects are allowed and are preserved in Place.
    -- FBX import can put a Motor6D *inside* COL whose other endpoint is an
    -- importer-only RootPart. The placed collider is anchored and receives an
    -- explicit world CFrame below, so that local connector is neither needed
    -- nor safe to retain. A connector owned elsewhere in the rig is different:
    -- cloning COL alone would silently change another subtree, so fail closed.
    for _, child in ipairs(template:GetDescendants()) do
        local linked = false
        if child:IsA("JointInstance") or child:IsA("WeldConstraint") then
            linked = child.Part0 == sourceCol or child.Part1 == sourceCol
        elseif child:IsA("Constraint") then
            linked = (child.Attachment0 ~= nil and child.Attachment0:IsDescendantOf(sourceCol))
                or (child.Attachment1 ~= nil and child.Attachment1:IsDescendantOf(sourceCol))
        end
        if linked and not child:IsDescendantOf(sourceCol) then
            error("опубликованный COL связан с другими частями rig; требуется проверка полного Sync")
        end
    end
    local part=ref.part
    local ratio=Vector3.new(part.Size.X/sourceVisual.Size.X,
        part.Size.Y/sourceVisual.Size.Y,part.Size.Z/sourceVisual.Size.Z)
    if ratio.X~=ratio.X or ratio.Y~=ratio.Y or ratio.Z~=ratio.Z
        or ratio.X<0.001 or ratio.Y<0.001 or ratio.Z<0.001
        or ratio.X>1000 or ratio.Y>1000 or ratio.Z>1000 then
        error("недопустимый масштаб для восстановления COL")
    end
    local relative=sourceVisual.CFrame:ToObjectSpace(sourceCol.CFrame)
    local col=sourceCol:Clone()
    local ok,reason=pcall(function()
        -- Do not leave cloned Motor6D/constraints pointing at the temporary
        -- published Model. Attachments/Bones and other collider-owned metadata
        -- remain intact; only mechanisms that cannot operate independently are
        -- removed from this explicitly anchored additive collider.
        for _, child in ipairs(col:GetDescendants()) do
            if child:IsA("JointInstance") or child:IsA("Constraint") then
                child:Destroy()
            end
        end
        local point=relative.Position
        col.CFrame=part.CFrame * CFrame.new(point.X*ratio.X,point.Y*ratio.Y,point.Z*ratio.Z) * relative.Rotation
        col.Size=Vector3.new(sourceCol.Size.X*ratio.X,sourceCol.Size.Y*ratio.Y,sourceCol.Size.Z*ratio.Z)
        col.Anchored=part.Anchored
        Physics.Apply(col,true,"PreciseConvexDecomposition",false)
        col.Transparency=1
        col.CastShadow=false
        col.TextureID=""
        local appearance=col:FindFirstChildOfClass("SurfaceAppearance")
        if appearance then appearance:Destroy() end
        col:SetAttribute("Game1DecoPhysicsOnly",true)
        local pivot=ref.root:GetPivot()
        col.Parent=ref.root
        if ref.root.PrimaryPart==nil then ref.root.WorldPivot=pivot end
        if ref.root:GetPivot()~=pivot then
            error("восстановление COL изменило pivot размещённой Model")
        end
    end)
    if not ok then
        col:Destroy()
        error(tostring(reason))
    end
    return col
end

function Repair.Apply(refs: {any}, ctx: any): any
    local eligible,blocked={},{}
    local allIds={}
    local originals=ctx.allRefs or refs
    -- Scan order is deterministic. Keep one existing copy's ID; fix the rest.
    for _, ref in ipairs(originals) do
        local key=ref.row.placementId
        if key~="" then allIds[key]=(allIds[key] or 0)+1 end
    end
    local kept={}
    for _, ref in ipairs(originals) do
        local key=ref.row.placementId
        if key~="" and not kept[key] then kept[key]=ref end
    end
    for _, ref in ipairs(refs) do
        if ref.row.ambiguous then
            table.insert(blocked,ref.row.key..": неоднозначное происхождение")
        elseif ref.needsCol and ref.oldVersion=="" then
            table.insert(blocked,ref.row.key..": невозможно подтвердить предыдущую Model-публикацию; COL Repair запрещён")
        elseif not ref.row.needsStructure and not ref.row.duplicateId then
            table.insert(blocked,ref.row.key..": структура уже актуальна; Repair не нужен")
        elseif not ref.root and not safeForWrapper(ref.part) then
            table.insert(blocked,ref.row.key..": связи меша запрещают изменение родителя")
        else
            table.insert(eligible,ref)
        end
    end
    if #eligible==0 then
        return {changed=0,skipped=blocked,
            note=if #blocked>0 then "Repair не изменил Place: причины пропуска в журнале"
                else "Нет подходящих размещений для Repair"}
    end
    local recording=ctx.history:TryBeginRecording(ctx.recordingName,"Repair Location Place Registry")
    if not recording then error("Studio Undo recording unavailable; Place unchanged") end
    local undo={}
    local changed=0
    local collidersCreated=0
    local loaded={}
    local ok,problem=pcall(function()
        for _,ref in ipairs(eligible) do
            local part=ref.part
            local parent=part.Parent
            local originalCFrame=part.CFrame
            local originalSize=part.Size
            local root=ref.root
            if not root then
                local group=if parent:IsA("Model") then parent else nil
                local groupPivot=if group then group:GetPivot() else nil
                local groupWorldPivot=if group then group.WorldPivot else nil
                local groupPrimary=if group then group.PrimaryPart else nil
                root=Instance.new("Model")
                root.Name="_Game1LocationRepairStaging"
                -- Register rollback BEFORE parenting the wrapper and moving
                -- the visual part. Even a failed assignment must roll back.
                local wrapper=root
                table.insert(undo,function()
                    if part.Parent==wrapper then part.Parent=parent end
                    wrapper:Destroy()
                    if group then
                        if groupPrimary then
                            group.PrimaryPart=groupPrimary
                        elseif groupWorldPivot then
                            group.WorldPivot=groupWorldPivot
                        end
                    end
                end)
                root.Parent=parent
                part.Parent=root
                root.PrimaryPart=part
                if group then
                    if groupPrimary then
                        -- Group PrimaryPart remains the SAME MeshPart, now a
                        -- descendant through the newly created child Model.
                        if group.PrimaryPart~=groupPrimary then
                            group.PrimaryPart=groupPrimary
                        end
                    elseif groupPivot then
                        -- Auto-pivot may change when a direct child is wrapped.
                        group.WorldPivot=groupPivot
                    end
                    if group.PrimaryPart~=groupPrimary or group:GetPivot()~=groupPivot then
                        error("grouping Model PrimaryPart/pivot changed during Repair")
                    end
                end
                ref.root=root
            end
            local oldName=root.Name
            local oldAttrs={}
            for _,name in ipairs({"Game1DecoInstanceId","Game1DecoAssetSlug",
                "Game1DecoRegistryModelAssetId","Game1DecoPublishedModelAssetId",
                "Game1DecoPublishedModelSha256","Game1DecoSyncHistory"}) do oldAttrs[name]=root:GetAttribute(name) end
            table.insert(undo,function()
                if root.Parent~=nil then
                    root.Name=oldName
                    for name,value in pairs(oldAttrs) do root:SetAttribute(name,value) end
                    for _,name in ipairs({"Game1DecoInstanceId","Game1DecoAssetSlug",
                        "Game1DecoRegistryModelAssetId","Game1DecoPublishedModelAssetId",
                        "Game1DecoPublishedModelSha256","Game1DecoSyncHistory"}) do
                        if oldAttrs[name]==nil then root:SetAttribute(name,nil) end
                    end
                end
            end)
            local pid=ref.row.placementId
            if pid=="" or (allIds[pid] or 0)>1 and kept[pid]~=ref then
                pid=assignedId(ctx.http)
            end
            root:SetAttribute("Game1DecoInstanceId",pid)
            root:SetAttribute("Game1DecoAssetSlug",ref.entry.slug)
            root:SetAttribute("Game1DecoRegistryModelAssetId",ref.entry.model)
            -- The copied model may carry metadata from a DIFFERENT asset.
            -- The confirmed complete published Mesh ID inventory takes
            -- precedence during explicit Repair. Never keep a false old Model
            -- ID: downstream geometry Sync would load the wrong source rig.
            if ref.oldVersion~="" then
                root:SetAttribute("Game1DecoPublishedModelAssetId",ref.oldVersion)
            end
            if ref.oldVersion==ref.entry.model and ref.entry.sha~="" then
                root:SetAttribute("Game1DecoPublishedModelSha256",ref.entry.sha)
            else
                root:SetAttribute("Game1DecoPublishedModelSha256",nil)
            end
            rename(root,ref.entry.slug,pid)
            -- A single visual MeshPart has the same public name as its Location
            -- Asset, without a unique suffix. Keep COL_* and multi-part authoring
            -- names intact: they encode physics and rig topology.
            local renamedPart, oldPartName = MeshNames.Normalize(root, ref.entry.slug)
            if renamedPart then
                table.insert(undo,function()
                    if renamedPart.Parent~=nil then renamedPart.Name=oldPartName end
                end)
            end
            if part.CFrame~=originalCFrame or part.Size~=originalSize then
                error("Repair changed existing geometry transform; rolling back")
            end
            -- Repair must also fix additive published collider changes when the
            -- visual MeshId is unchanged between Model publications.
            if ref.needsCol then
                local template=loaded[ref.entry.slug]
                if not template then
                    template=ctx.loader:loadForMeshInventory(ref.entry.model,ref.entry.slug)
                    loaded[ref.entry.slug]=template
                end
                local beforeMeshes=History.Describe(ref.oldVersion,root).meshes
                local made=restoreCol(ref,template)
                if made then
                    table.insert(undo,function() made:Destroy() end)
                    collidersCreated+=1
                    -- Both the previously published single visual and the
                    -- restored COL now match the CURRENT published Mesh inventory.
                    -- Never stamp the latest version without this verification.
                    if not Published.CurrentShape(ref.entry,root) then
                        error("восстановленный COL не соответствует актуальному опубликованному rig")
                    end
                    local beforePhysics=Physics.CaptureLocationModel(root,{[part.Name]=true})
                    table.insert(undo,function() Physics.RestoreLocationModel(beforePhysics) end)
                    Physics.Apply(part,false,"Box",part.DoubleSided)
                    root:SetAttribute("Game1DecoPublishedModelAssetId",ref.entry.model)
                    root:SetAttribute("Game1DecoPublishedModelSha256",ref.entry.sha)
                    PlacementHistory.Append(root,ctx.http,ref.entry.slug,{{
                        kind=if ref.oldVersion==ref.entry.model then "collider_restore" else "model",
                        oldId=ref.oldVersion,newId=ref.entry.model,count=1}},
                        beforeMeshes,History.Describe(ref.entry.model,root).meshes)
                end
            end
            changed+=1
        end
    end)
    -- Destroy staged published references on both success AND failure. They
    -- must never leak across repeated Studio Repair attempts.
    for _,template in pairs(loaded) do pcall(function() template:Destroy() end) end
    if not ok then
        for i=#undo,1,-1 do pcall(undo[i]) end
        ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Cancel)
        error("Repair отменён: "..tostring(problem))
    end
    ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Commit)
    return {changed=changed,collidersCreated=collidersCreated,skipped=blocked,undo=true,
        note="Repair обновил структуру/ID и восстановил COL: "..tostring(collidersCreated)
            .."; перед Sync требуется новый Scan"}
end

return Repair

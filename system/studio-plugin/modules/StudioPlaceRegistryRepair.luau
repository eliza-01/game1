-- Studio-only explicit, undo-recorded migration of Location placements.
-- Hand-made grouping containers are retained; only matching visual parts get wrappers.
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local MeshNames = require(script.Parent.StudioLocationMeshNames)
local Repair = {}

local function safeForWrapper(part: MeshPart): boolean
    -- Parenting parts with external attachments/joints changes their authoring
    -- lifecycle; do not guess which other system owns such connections.
    if part.Parent:IsA("Model") and part.Parent.PrimaryPart==part then
        return false -- Don't detach the manually grouped Model's pivot anchor.
    end
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
    if not ref.root or ref.row.needsMesh or not ref.needsCol then return false end
    local sourceVisual: MeshPart?=nil
    local sourceCol: MeshPart?=nil
    for _, child in ipairs(template:GetDescendants()) do
        if child:IsA("MeshPart") then
            if child.Name:lower()=="col_mesh" or child.Name:lower():match("^col_") then
                if sourceCol then error("more than one collider; manual repair required") end
                sourceCol=child
            else
                if sourceVisual then error("multi-part rig requires manual collider repair") end
                sourceVisual=child
            end
        elseif child:IsA("Bone") or child:IsA("Motor6D") then
            error("rigged geometry requires full geometry sync before restoring COL")
        end
    end
    if not sourceVisual or not sourceCol or #ref.visuals~=1 then
        error("no unique published visual+COL pair")
    end
    local part=ref.part
    local ratio=Vector3.new(part.Size.X/sourceVisual.Size.X,
        part.Size.Y/sourceVisual.Size.Y,part.Size.Z/sourceVisual.Size.Z)
    if ratio.X<=0 or ratio.Y<=0 or ratio.Z<=0 then error("invalid collider size ratio") end
    local relative=sourceVisual.CFrame:ToObjectSpace(sourceCol.CFrame)
    local col=sourceCol:Clone()
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
    col.Parent=ref.root
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
        elseif not ref.root and not safeForWrapper(ref.part) then
            table.insert(blocked,ref.row.key..": связи меша запрещают изменение родителя")
        else
            table.insert(eligible,ref)
        end
    end
    if #eligible==0 then return {changed=0,skipped=blocked} end
    local recording=ctx.history:TryBeginRecording(ctx.recordingName,"Repair Location Place Registry")
    if not recording then error("Studio Undo recording unavailable; Place unchanged") end
    local undo={}
    local changed=0
    local ok,problem=pcall(function()
        local loaded={}
        for _,ref in ipairs(eligible) do
            local part=ref.part
            local parent=part.Parent
            local originalCFrame=part.CFrame
            local originalSize=part.Size
            local root=ref.root
            if not root then
                local groupPivot=if parent:IsA("Model") then parent:GetPivot() else nil
                local groupWorldPivot=if parent:IsA("Model") then parent.WorldPivot else nil
                root=Instance.new("Model")
                root.Name="_Game1LocationRepairStaging"
                root.Parent=parent
                part.Parent=root
                root.PrimaryPart=part
                if groupPivot and parent:IsA("Model") and not parent.PrimaryPart then
                    -- A manually grouped Model's auto-pivot must not drift
                    -- when its visual children become standalone placements.
                    parent.WorldPivot=groupPivot
                end
                table.insert(undo,function()
                    part.Parent=parent
                    root:Destroy()
                    if groupWorldPivot and parent:IsA("Model") and not parent.PrimaryPart then
                        parent.WorldPivot=groupWorldPivot
                    end
                end)
                changed+=1
                ref.root=root
            end
            local oldName=root.Name
            local oldAttrs={}
            for _,name in ipairs({"Game1DecoInstanceId","Game1DecoAssetSlug",
                "Game1DecoRegistryModelAssetId","Game1DecoPublishedModelAssetId",
                "Game1DecoPublishedModelSha256"}) do oldAttrs[name]=root:GetAttribute(name) end
            table.insert(undo,function()
                if root.Parent~=nil then
                    root.Name=oldName
                    for name,value in pairs(oldAttrs) do root:SetAttribute(name,value) end
                    for _,name in ipairs({"Game1DecoInstanceId","Game1DecoAssetSlug",
                        "Game1DecoRegistryModelAssetId","Game1DecoPublishedModelAssetId",
                        "Game1DecoPublishedModelSha256"}) do
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
            if ref.oldVersion~="" and root:GetAttribute("Game1DecoPublishedModelAssetId")==nil then
                root:SetAttribute("Game1DecoPublishedModelAssetId",ref.oldVersion)
            end
            if ref.oldVersion==ref.entry.model and ref.entry.sha~="" then
                root:SetAttribute("Game1DecoPublishedModelSha256",ref.entry.sha)
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
            changed+=1
            -- Rebuilding a rig AND COL in a single repair would cause its historical
            -- multiset to stop matching. The new COL arrives with explicit Sync.
            if ref.needsCol and not ref.row.needsMesh then
                local template=loaded[ref.entry.slug]
                if not template then
                    template=ctx.loader:loadForMeshInventory(ref.entry.model,ref.entry.slug)
                    loaded[ref.entry.slug]=template
                end
                local made=restoreCol(ref,template)
                if made then
                    table.insert(undo,function() made:Destroy() end)
                end
            end
        end
        for _,template in pairs(loaded) do template:Destroy() end
    end)
    if not ok then
        for i=#undo,1,-1 do pcall(undo[i]) end
        ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Cancel)
        error("Repair отменён: "..tostring(problem))
    end
    ctx.history:FinishRecording(recording,Enum.FinishRecordingOperation.Commit)
    return {changed=changed,skipped=blocked,undo=true,
        note="Repair обновил структуру/ID; перед Sync требуется новый Scan"}
end

return Repair

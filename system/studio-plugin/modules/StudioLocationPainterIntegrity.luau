-- Shared, read-only integrity contract for LandscapePainter-owned Location Assets.
-- The Painter owns placement, tether, sway and effects. The Location registry
-- owns the published mesh appearance. Never transfer ownership between them.
local Integrity = {}

local function check(model: Model): (boolean, string)
    if model:GetAttribute("LandscapeAuthoringTool") ~= "Game1LandscapePainter" then
        return false, "missing LandscapePainter owner marker"
    end
    local kind = model:GetAttribute("LandscapeAnchorKind")
    if kind ~= "stem" and kind ~= "surface" then
        return false, "unknown LandscapePainter anchor kind"
    end
    local tether = model:GetAttribute("LandscapeTetherEnabled") == true
    local sway = model:GetAttribute("LandscapeSwayEnabled") == true
    local line = model:FindFirstChild("LandscapeAttachmentLine")
    if tether then
        if not line or not line:IsA("Part")
            or line:GetAttribute("Game1LandscapeAttachment") ~= true then
            return false, "missing or invalid LandscapeAttachmentLine; repair with LandscapePainter Apply"
        end
    elseif line ~= nil then
        return false, "orphan LandscapeAttachmentLine; repair with LandscapePainter Apply"
    end
    local swayTarget = model:FindFirstChild("LandscapeSwayTarget")
    if tether and sway then
        if not swayTarget or not swayTarget:IsA("BasePart")
            or swayTarget:GetAttribute("Game1LandscapeSwayTarget") ~= true then
            return false, "missing LandscapeSwayTarget; repair with LandscapePainter Apply"
        end
    elseif swayTarget ~= nil then
        return false, "obsolete LandscapeSwayTarget; repair with LandscapePainter Apply"
    end
    if kind == "stem" then
        local link = model:FindFirstChild("LandscapeAnchorStem")
        local parent = model.Parent
        local branch = if parent and parent.Name == "Attachments" then parent.Parent else nil
        if not branch or not branch:IsA("Model")
            or branch:GetAttribute("AuthoringTool") ~= "Game1LandscapePainter"
            or not link or not link:IsA("ObjectValue") or not link.Value
            or not link.Value:IsDescendantOf(branch) then
            return false, "missing/invalid LandscapeAnchorStem; repair anchor in LandscapePainter"
        end
        if model:GetAttribute("LandscapeBranchStrokeId") ~= branch:GetAttribute("StrokeId") then
            return false, "LandscapePainter branch stroke identity changed"
        end
        if typeof(model:GetAttribute("LandscapeStemLocalPoint")) ~= "Vector3"
            or typeof(model:GetAttribute("LandscapeStemLocalNormal")) ~= "Vector3" then
            return false, "missing local stem anchor frame"
        end
    end
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:GetAttribute("Game1LandscapePhysics") == true then
            return false, "retired LandscapePainter physics detected; use Painter Apply"
        end
    end
    return true, "current"
end

Integrity.Check = check

-- Preserve *all* authored descendants (including unknown effects) and their
-- parents, not just a whitelist of Fire/Light/Bone classes. SurfaceAppearance
-- is explicitly owned by the centralized appearance policy and may be deleted.
function Integrity.Capture(model: Model): any
    local entries = {}
    local count = 0
    for _, descendant in ipairs(model:GetDescendants()) do
        if not descendant:IsA("SurfaceAppearance")
            and descendant:GetAttribute("Game1LocationCollisionOwned") ~= true then
            count += 1
            if count > 512 then error("LandscapePainter assembly too large for safe appearance Sync") end
            local snap = {parent=descendant.Parent, class=descendant.ClassName}
            if descendant:IsA("BasePart") then
                snap.cframe=descendant.CFrame
                snap.size=descendant.Size
                snap.meshId=if descendant:IsA("MeshPart") then descendant.MeshId else nil
                snap.anchored=descendant.Anchored
                snap.canCollide=descendant.CanCollide
                snap.canQuery=descendant.CanQuery
            elseif descendant:IsA("Bone") or descendant:IsA("Attachment") then
                snap.cframe=descendant.CFrame
            elseif descendant:IsA("ObjectValue") then
                snap.value=descendant.Value
            end
            if descendant:IsA("Light") then
                snap.effect={descendant.Enabled,descendant.Brightness,descendant.Color,
                    descendant.Range,descendant.Shadows}
            elseif descendant:IsA("Fire") then
                snap.effect={descendant.Enabled,descendant.Heat,descendant.Size,
                    descendant.Color,descendant.SecondaryColor}
            elseif descendant:IsA("ParticleEmitter") then
                snap.effect={descendant.Enabled,descendant.Texture,descendant.Rate,
                    descendant.Lifetime,descendant.Speed}
            elseif descendant:IsA("Beam") then
                snap.effect={descendant.Enabled,descendant.Attachment0,
                    descendant.Attachment1,descendant.Texture}
            elseif descendant:IsA("WeldConstraint") then
                snap.effect={descendant.Enabled,descendant.Part0,descendant.Part1}
            elseif descendant:IsA("JointInstance") then
                snap.effect={descendant.Part0,descendant.Part1,descendant.C0,descendant.C1}
            end
            entries[descendant]=snap
        end
    end
    return {root=model,parent=model.Parent,pivot=model:GetPivot(),scale=model:GetScale(),entries=entries,count=count,
        stroke=model:GetAttribute("LandscapeBranchStrokeId"),
        assetSlug=model:GetAttribute("LandscapeAssetSlug"),
        modelAssetId=model:GetAttribute("LandscapeModelAssetId")}
end

function Integrity.AssertUnchanged(snapshot: any, allowedVisualPhysics: any?)
    local model = snapshot.root
    if model.Parent~=snapshot.parent or model:GetPivot()~=snapshot.pivot or model:GetScale()~=snapshot.scale
        or model:GetAttribute("LandscapeBranchStrokeId")~=snapshot.stroke
        or model:GetAttribute("LandscapeAssetSlug")~=snapshot.assetSlug
        or model:GetAttribute("LandscapeModelAssetId")~=snapshot.modelAssetId then
        error("LandscapePainter root/placement changed during appearance Sync")
    end
    local seen=0
    for _, descendant in ipairs(model:GetDescendants()) do
        if not descendant:IsA("SurfaceAppearance")
            and descendant:GetAttribute("Game1LocationCollisionOwned") ~= true then
            local before=snapshot.entries[descendant]
            if not before or before.parent~=descendant.Parent or before.class~=descendant.ClassName then
                error("LandscapePainter hierarchy/effect changed during appearance Sync")
            end
            seen+=1
            if descendant:IsA("BasePart") then
                if descendant.CFrame~=before.cframe or descendant.Size~=before.size
                    or descendant.Anchored~=before.anchored
                    or (not (type(allowedVisualPhysics)=="table" and allowedVisualPhysics[descendant]==true)
                        and (descendant.CanCollide~=before.canCollide
                            or descendant.CanQuery~=before.canQuery))
                    or (descendant:IsA("MeshPart") and descendant.MeshId~=before.meshId) then
                    error("LandscapePainter geometry/physics changed during appearance Sync")
                end
            elseif descendant:IsA("Bone") or descendant:IsA("Attachment") then
                if descendant.CFrame~=before.cframe then error("LandscapePainter rig/socket changed during appearance Sync") end
            elseif descendant:IsA("ObjectValue") and descendant.Value~=before.value then
                error("LandscapePainter stem link changed during appearance Sync")
            end
            local previous=before.effect
            if previous then
                local current
                if descendant:IsA("Light") then
                    current={descendant.Enabled,descendant.Brightness,descendant.Color,
                        descendant.Range,descendant.Shadows}
                elseif descendant:IsA("Fire") then
                    current={descendant.Enabled,descendant.Heat,descendant.Size,
                        descendant.Color,descendant.SecondaryColor}
                elseif descendant:IsA("ParticleEmitter") then
                    current={descendant.Enabled,descendant.Texture,descendant.Rate,
                        descendant.Lifetime,descendant.Speed}
                elseif descendant:IsA("Beam") then
                    current={descendant.Enabled,descendant.Attachment0,
                        descendant.Attachment1,descendant.Texture}
                elseif descendant:IsA("WeldConstraint") then
                    current={descendant.Enabled,descendant.Part0,descendant.Part1}
                elseif descendant:IsA("JointInstance") then
                    current={descendant.Part0,descendant.Part1,descendant.C0,descendant.C1}
                end
                if not current or #current~=#previous then
                    error("LandscapePainter light/effect/constraint structure changed")
                end
                for i=1,#previous do
                    if current[i]~=previous[i] then
                        error("LandscapePainter light/effect/constraint settings changed")
                    end
                end
            end
        end
    end
    if seen~=snapshot.count then error("LandscapePainter descendant was removed during appearance Sync") end
    local ok, reason = check(model)
    if not ok then error("LandscapePainter structural integrity failed: "..reason) end
end

return table.freeze(Integrity)

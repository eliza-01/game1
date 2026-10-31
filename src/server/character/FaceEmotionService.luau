--!strict
-- Server-owned replicated presentation state. No client remote and no combat authority.
local Contract = require(game:GetService("ReplicatedStorage").Game1Shared.character.FaceEmotionContract)
local Service = {}
local Registry=require(game:GetService("ReplicatedStorage").Game1Shared.character.CharacterAnimationRegistry)
local bound=setmetatable({}, {__mode="k"})
function Service.Set(character: Model, emotion: string?)
    assert(emotion == nil or Contract.names[emotion], "unsupported face emotion")
    character:SetAttribute(Contract.attribute, emotion)
end

function Service.Bind(character: Model)
    if bound[character] or not character:FindFirstChild("eyes_01_l",true) or not character:FindFirstChild("eyes_01_r",true) then return end
    local animator=character:FindFirstChildWhichIsA("Animator",true)
    local profile=Registry.profiles[tostring(character:GetAttribute("AnimationProfileId") or "")]
    if not animator or not profile then return end
    local context={connections={},loaded={},current=nil}
    bound[character]=context
    local function refresh()
        local state=character:GetAttribute(Contract.attribute) or (if character:GetAttribute("InCombat")==true then "combat_idle" else "idle")
        local rows=profile.emotions and profile.emotions[state]
        local descriptor=rows and rows[1]
        local doc=descriptor and descriptor.document
        local track=nil
        if doc and doc.mode=="skeletal" and descriptor.animationId~="" and
            (not doc.rig or tostring(doc.rig.asset_id)==tostring(character:GetAttribute("CharacterRigAssetId"))) then
            local entry=context.loaded[descriptor.clipId]
            if not entry then
                local animation=Instance.new("Animation");animation.AnimationId=descriptor.animationId
                local ok,result=pcall(function() return animator:LoadAnimation(animation) end)
                if ok then
                    entry={animation=animation,track=result};context.loaded[descriptor.clipId]=entry
                    result.Looped=descriptor.looped;result.Priority=Enum.AnimationPriority.Action2
                else animation:Destroy();warn("[game1][face] cannot load emotion: "..tostring(result)) end
            end
            track=entry and entry.track
        end
        if context.current~=track then
            if context.current then context.current:Stop(.1) end
            context.current=track
            if track then track:Play(.1) end
        end
    end
    table.insert(context.connections,character:GetAttributeChangedSignal(Contract.attribute):Connect(refresh))
    table.insert(context.connections,character:GetAttributeChangedSignal("InCombat"):Connect(refresh))
    table.insert(context.connections,character.Destroying:Connect(function()
        for _,connection in context.connections do connection:Disconnect() end
        for _,entry in context.loaded do entry.track:Stop(0);entry.track:Destroy();entry.animation:Destroy() end
        bound[character]=nil
    end))
    refresh()
end
return table.freeze(Service)

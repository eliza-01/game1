--!strict
-- Player presentation only. No gameplay timing is driven by cosmetic clip events.
local Players=game:GetService("Players")
local RunService=game:GetService("RunService")
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("character")
local Timeline=require(Shared:WaitForChild("AnimationEventTimeline"))
local Contract=require(Shared:WaitForChild("FaceEmotionContract"))
local Resolver=require(script.Parent:WaitForChild("AnimationResolver"))
local Presenter=require(script.Parent:WaitForChild("FacePresentation"))
local CombinedPresenter=require(script.Parent:WaitForChild("CombinedFacePresentation"))
local Idle=require(Shared:WaitForChild("FaceIdleDefaults"))
local Controller={}
local started=false
local sessions={}

local function identity(value: string): string
    return string.match(value,"%d+") or value
end

function Controller.Bind(character: Model, descriptors: {any}?)
    if sessions[character] then return sessions[character] end
    local presenter=Presenter.new(character) or CombinedPresenter.new(character)
    local animator=character:FindFirstChildWhichIsA("Animator",true)
    if not presenter or not animator then
        if presenter then presenter:Destroy() end
        return nil
    end
    local byAsset,procedural={},{}
    for _,descriptor in descriptors or Resolver.ListForCharacter(character,true) do
        local doc=descriptor.document
        if doc and doc.schema_version==1 then
            -- Rig-specific motion must never silently run on a different publication.
            local target=doc.rig
            local asset=character:GetAttribute("CharacterRigAssetId")
            local compatible=not target or tostring(target.asset_id)==tostring(asset)
            if compatible then
                if doc.mode=="procedural" then procedural[string.gsub(doc.clip_name,"^emotions_","")]=doc
                elseif descriptor.animationId~="" then byAsset[identity(descriptor.animationId)]=doc end
            end
        end
    end
    if presenter.SetIdlePhase and not procedural.idle then procedural.idle=Idle.document end
    local self={character=character,presenter=presenter,tracks={},connections={},destroyed=false,
        owner=nil,bodyOwner=nil,state=nil,clock=0,cycle=0,cursor=nil,procedural=procedural,byAsset=byAsset,serial=0}
    sessions[character]=self
    local function watch(track)
        local doc=track.Animation and byAsset[identity(track.Animation.AnimationId)]
        if not doc or self.tracks[track] then return end
        self.serial+=1
        local entry={doc=doc,cycle=0,cursor=Timeline.new(doc),serial=self.serial,previous=nil}
        entry.loop=track.DidLoop:Connect(function() entry.cycle+=1 end)
        entry.stop=track.Stopped:Connect(function()
            entry.loop:Disconnect();entry.stop:Disconnect();self.tracks[track]=nil
        end)
        self.tracks[track]=entry
    end
    table.insert(self.connections,animator.AnimationPlayed:Connect(watch))
    for _,track in animator:GetPlayingAnimationTracks() do watch(track) end
    function self:Destroy()
        if self.destroyed then return end
        self.destroyed=true
        for _,connection in self.connections do connection:Disconnect() end
        for _,entry in self.tracks do entry.loop:Disconnect();entry.stop:Disconnect() end
        table.clear(self.tracks);self.presenter:Destroy();sessions[character]=nil
    end
    table.insert(self.connections,character.Destroying:Connect(function() self:Destroy() end))
    return self
end

local function better(track,entry,best,bestEntry)
    if not best then return true end
    local rank=if track.Priority==Enum.AnimationPriority.Core then -1 else track.Priority.Value
    local bestRank=if best.Priority==Enum.AnimationPriority.Core then -1 else best.Priority.Value
    if rank~=bestRank then return rank>bestRank end
    if math.abs(track.WeightCurrent-best.WeightCurrent)>.001 then return track.WeightCurrent>best.WeightCurrent end
    return entry.serial>bestEntry.serial
end

function Controller.StepSession(self,delta: number)
    if self.destroyed then return end
    local face,faceEntry,body,bodyEntry=nil,nil,nil,nil
    for track,entry in self.tracks do
        if track.IsPlaying and track.WeightCurrent>.05 then
            if string.sub(entry.doc.clip_name,1,9)=="emotions_" then
                if better(track,entry,face,faceEntry) then face,faceEntry=track,entry end
            elseif better(track,entry,body,bodyEntry) then body,bodyEntry=track,entry end
        end
    end
    local state=tostring(self.character:GetAttribute(Contract.attribute) or (if self.character:GetAttribute("InCombat")==true then "combat_idle" else "idle"))
    local doc=not face and self.procedural[state] or nil
    local changed=self.owner~=face or self.state~=state
    local bodyChanged=self.bodyOwner~=body
    if self.presenter.SetIdlePhase then self.presenter:SetIdlePhase(nil) end
    if changed then
        self.presenter:Reset();self.clock=0;self.cycle=0
        self.cursor=doc and Timeline.new(doc) or nil
        self.owner=face;self.state=state
        if faceEntry then
            faceEntry.cursor:Reset();faceEntry.previous=nil
        elseif not doc then self.presenter:Event({name="face_state",parameters={name=state}}) end
    end
    self.bodyOwner=body
    if bodyChanged and bodyEntry then bodyEntry.cursor:Reset();bodyEntry.previous=nil end
    local presentationDelta=delta
    local function advance(track,entry,blinkOnly)
        local position=track.TimePosition
        local elapsed=if entry.previous then (entry.cycle-entry.previous.cycle)*(entry.doc.duration or track.Length)+position-entry.previous.position else 0
        local seek=(entry.previous==nil and position>.25) or elapsed<0 or elapsed>math.max(.25,delta*math.abs(track.Speed)*2+.05)
        local events,reset=entry.cursor:Advance(position,entry.cycle,seek)
        if reset and not blinkOnly then self.presenter:Reset() end
        for _,event in events do
            local age=position-event.time
            if age<0 then age+=(entry.doc.duration or track.Length) end
            if (not blinkOnly or event.name=="blink") and (event.name~="blink" or age<(event.parameters.duration or .16)) then
                self.presenter:Event(event,age,if blinkOnly then presentationDelta else (if seek then 0 else math.max(0,elapsed)))
            end
        end
        entry.previous={position=position,cycle=entry.cycle}
        return if seek then 0 else math.max(0,elapsed)
    end
    if faceEntry then presentationDelta=advance(face,faceEntry,false)
    elseif doc and self.cursor then
        local duration=doc.duration or ((doc.frame_end-doc.frame_start)/doc.fps)
        self.clock+=delta
        local cycle=if doc.looped then math.floor(self.clock/duration) else 0
        local position=if doc.looped then self.clock%duration else math.min(self.clock,duration)
        local events=self.cursor:Advance(position,cycle)
        if doc==Idle.document then self.presenter:SetIdlePhase(position) end
        for _,event in events do
            local age=(position-event.time)%duration
            if event.name~="blink" or age<(event.parameters.duration or .16) then self.presenter:Event(event,age,delta) end
        end
    end
    if bodyEntry then
        local elapsed=advance(body,bodyEntry,faceEntry~=nil or doc~=nil)
        if not faceEntry and not doc then presentationDelta=elapsed end
    end
    self.presenter:Step(presentationDelta,faceEntry==nil)
end

function Controller.Start()
    if started then return end
    started=true
    local links={}
    local function watchPlayer(player)
        local characterLinks={}
        local function bind(character)
            local pending=false
            local function tryBind()
                if pending then return end
                pending=true
                task.defer(function()
                    pending=false
                    if character.Parent and not sessions[character] then Controller.Bind(character) end
                end)
            end
            characterLinks[character]=character.DescendantAdded:Connect(tryBind)
            tryBind()
        end
        links[player]={player.CharacterAdded:Connect(bind),player.CharacterRemoving:Connect(function(character)
            if characterLinks[character] then characterLinks[character]:Disconnect();characterLinks[character]=nil end
            if sessions[character] then sessions[character]:Destroy() end
        end)}
        links[player].characterLinks=characterLinks
        if player.Character then bind(player.Character) end
    end
    Players.PlayerAdded:Connect(watchPlayer)
    Players.PlayerRemoving:Connect(function(player)
        local link=links[player]
        if not link then return end
        for _,connection in ipairs(link) do connection:Disconnect() end
        for character,connection in link.characterLinks do
            connection:Disconnect();if sessions[character] then sessions[character]:Destroy() end
        end
        links[player]=nil
    end)
    for _,player in Players:GetPlayers() do watchPlayer(player) end
    RunService.PreAnimation:Connect(function()
        for _,session in sessions do session.presenter:BeforeAnimation() end
    end)
    RunService.PreSimulation:Connect(function(delta)
        for _,session in sessions do Controller.StepSession(session,delta) end
    end)
end
return Controller

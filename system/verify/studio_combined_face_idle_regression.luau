-- Studio fixture: existing combined eyes, no new model/animation asset publication.
local client=nil
for _,object in game.StarterPlayer.StarterPlayerScripts:GetChildren() do
    if object.Name=="Game1Client" and object:IsA("LocalScript") then client=object end
end
assert(client,"client source is missing")
local modules=client.character.animation:Clone();modules.Name="combined_idle_test_modules";modules.Parent=game.ServerStorage
local Controller=require(modules.FaceAnimationController)
local Timeline=require(game.ReplicatedStorage.Game1Shared.character.AnimationEventTimeline)
local model=Instance.new("Model");model.Name="combined_idle_fixture"
local session=nil
local ok,result=xpcall(function()
    local carrier=Instance.new("Part");carrier.Name="rig_carrier";carrier.Anchored=true;carrier.Parent=model
    local head=Instance.new("Bone");head.Name="face_head";head.Parent=carrier
    local left=Instance.new("Bone");left.Name="face_eye_ctrl_l";left.CFrame=CFrame.new(-.3,1,0);left.Parent=head
    local right=Instance.new("Bone");right.Name="face_eye_ctrl_r";right.CFrame=CFrame.new(.3,1,0);right.Parent=head
    local eyes=Instance.new("Part");eyes.Name="eyes_01";eyes.Size=Vector3.new(.7,.22,.03);eyes.CFrame=CFrame.new(0,1,0);eyes.Anchored=true;eyes.Parent=model
    local host=Instance.new("AnimationController");host.Parent=model;Instance.new("Animator").Parent=host
    model.Parent=workspace
    session=assert(Controller.Bind(model,{}),"combined eyes did not bind")
    local minimum,maximum,travel=math.huge,0,0
    for _=1,300 do
        session.presenter:BeforeAnimation();Controller.StepSession(session,1/60)
        minimum=math.min(minimum,session.presenter.mesh.Size.Y)
        maximum=math.max(maximum,session.presenter.mesh.Size.Y)
        assert(math.abs(session.presenter.mesh.Size.X-eyes.Size.X)<1e-6,"blink changed eye spacing")
        travel=math.max(travel,left.Transform.Position.Magnitude)
    end
    assert(minimum<.025 and maximum>.21,"idle failed to blink and reopen")
    assert(travel>.02,"idle failed to move its control bones")
    assert(eyes.Size==Vector3.new(.7,.22,.03),"source size changed")
    local clock=session.clock
    local track={IsPlaying=true,WeightCurrent=1,Priority=Enum.AnimationPriority.Movement,TimePosition=0,Length=10,Speed=1}
    session.tracks[track]={doc={clip_name="base_idle",duration=10,events={}},cursor=Timeline.new({duration=10,events={}}),cycle=0,serial=1}
    session.presenter:BeforeAnimation();Controller.StepSession(session,.02)
    assert(session.clock>clock,"body animation restarted face idle")
    session.tracks[track]=nil
    model:SetAttribute("FaceEmotion","closed");session.presenter:BeforeAnimation();Controller.StepSession(session,.02)
    assert(session.presenter.mesh.Size.Y<.025,"closed pose did not work")
    session:Destroy();session=nil
    assert(eyes.LocalTransparencyModifier==0,"original visibility not restored")
    assert(left.Transform.Position.Magnitude<1e-6 and right.Transform.Position.Magnitude<1e-6,"bone overlay remained")
    return {ok=true,minimumHeight=minimum,maximumHeight=maximum,boneTravel=travel,bodyClockIndependent=true}
end,debug.traceback)
if session then session:Destroy() end
model:Destroy();modules:Destroy()
assert(ok,result)
return result

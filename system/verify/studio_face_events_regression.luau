-- Run in Studio Edit or Play Server. Creates and removes only its own fixture.
local Shared=game.ReplicatedStorage.Game1Shared.character
local Timeline=require(Shared.AnimationEventTimeline)
local client=nil
for _,object in game.StarterPlayer.StarterPlayerScripts:GetChildren() do
    if object.Name=="Game1Client" and object:IsA("LocalScript") then client=object end
end
assert(client,"active client script is missing")
local moduleFolder=client.character.animation:Clone()
moduleFolder.Name="face_regression_modules";moduleFolder.Parent=game.ServerStorage
local Presentation=require(moduleFolder.FacePresentation)
local Controller=require(moduleFolder.FaceAnimationController)
local doc={schema_version=1,clip_name="emotions_blink",mode="procedural",fps=30,frame_start=1,frame_end=31,looped=true,
    events={{time=0,name="face_state",parameters={name="idle"}},{time=.25,name="blink",parameters={duration=.2}},
        {time=.5,name="eyes_set",parameters={name="normal"}}}}
local cursor=Timeline.new(doc)
assert(#cursor:Advance(0,0)==1,"time-zero state")
assert(#cursor:Advance(.25,0)==1,"blink boundary")
assert(#cursor:Advance(.25,0)==0,"pause duplicates events")
assert(#cursor:Advance(.8,0)==1,"forward crossing")
assert(#cursor:Advance(.1,1)==1,"loop did not restore time-zero event")
local seek,reset=cursor:Advance(.05,1,true)
assert(reset and #seek==1 and seek[1].name~="blink","seek replayed a blink")
local cycles=Timeline.new(doc);cycles:Advance(.1,0)
assert(#cycles:Advance(.3,4)==4,"hitch work must be bounded to two partial cycles")
cursor:Reset();assert(#cursor:Advance(0,0)==1,"restart")
local fixture=Instance.new("Model");fixture.Name="face_events_fixture"
local templates=Instance.new("Folder")
local spiral=Instance.new("Part");spiral.Name="eyes_01_spiral";spiral:SetAttribute("FaceLocalCFrame",CFrame.identity);spiral.Parent=templates
local originals={}
local ok,reason=xpcall(function()
    local carrier=Instance.new("Part");carrier.Name="rig_carrier";carrier.Anchored=true;carrier.Parent=fixture
    for _,side in {"l","r"} do
        for _,kind in {"eye","brow"} do
            local bone=Instance.new("Bone");bone.Name="face_"..kind.."_"..side;bone.CFrame=CFrame.new(if side=="l" then -.2 else .2,1,0);bone.Parent=carrier
            local part=Instance.new("Part");part.Name=(if kind=="eye" then "eyes_01_" else "eyebrows_01_")..side
            part.Size=Vector3.new(.1,.2,.04);part.CFrame=bone.WorldCFrame;part.Anchored=true;part.Parent=fixture
            table.insert(originals,part)
        end
    end
    local host=Instance.new("AnimationController");host.Parent=fixture;Instance.new("Animator").Parent=host
    fixture.Parent=workspace
    local presenter=assert(Presentation.new(fixture,templates),"missing valid four-part rig")
    presenter:Event({name="blink",parameters={duration=.2}})
    presenter:Step(.1,true)
    assert(presenter.entries.eye_l.mesh.Size.Y<.025,"blink did not close")
    presenter:BeforeAnimation();presenter:Step(0,true)
    assert(presenter.entries.eye_l.mesh.Size.Y<.025,"pause advanced blink")
    presenter:BeforeAnimation();presenter:Step(.1,true)
    assert(math.abs(presenter.entries.eye_l.mesh.Size.Y-.2)<1e-5,"blink failed to reopen")
    presenter:Event({name="face_state",parameters={name="combat_idle"}});presenter:BeforeAnimation();presenter:Step(.1,true)
    assert(math.abs(presenter.entries.eye_l.mesh.Size.Y-.2)<1e-5,"combat narrowed eyes")
    presenter:Event({name="face_state",parameters={name="indignant_surprise"}});presenter:BeforeAnimation();presenter:Step(.1,true)
    assert(presenter.entries.eye_r.bone.Transform==CFrame.identity,"indignant changed second eye")
    presenter:Reset();presenter:Event({name="eyes_set",parameters={name="spiral"}})
    presenter:Event({name="eyes_spin_start",parameters={degrees_per_second=180}});presenter:Step(.25,true)
    local left=presenter.temporary.l.CFrame.Rotation
    assert(left.RightVector:Dot(presenter.temporary.r.CFrame.RightVector)<-.99999 and
        left.UpVector:Dot(presenter.temporary.r.CFrame.UpVector)<-.99999,"right spiral phase is not 180 degrees")
    presenter:BeforeAnimation();presenter:Step(.25,true)
    local _,rotation=left:ToObjectSpace(presenter.temporary.l.CFrame.Rotation):ToAxisAngle()
    assert(math.abs(rotation-math.pi/4)<1e-5,"spiral did not rotate synchronously")
    presenter:Event({name="eyes_spin_stop"});presenter:Event({name="eyes_set",parameters={name="normal"}})
    assert(next(presenter.temporary)==nil,"spiral copies remain after return")
    presenter:Destroy()
    for _,original in originals do assert(original.LocalTransparencyModifier==0,"visibility not restored") end
    local session=assert(Controller.Bind(fixture,{{animationId="",document=doc}}))
    fixture:SetAttribute("FaceEmotion","blink")
    Controller.StepSession(session,.25)
    session.presenter:BeforeAnimation();Controller.StepSession(session,.1)
    assert(session.presenter.entries.eye_l.mesh.Size.Y<.025,"document blink not dispatched")
    session:Destroy();assert(session.destroyed,"cleanup")
end,debug.traceback)
fixture:Destroy()
templates:Destroy();moduleFolder:Destroy()
assert(ok,reason)
return {ok=true,checks=18,scope="timeline, rigid fixture, document dispatch, spiral phase/spin/return; no cloud upload"}

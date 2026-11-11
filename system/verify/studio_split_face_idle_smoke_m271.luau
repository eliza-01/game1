-- Studio-only manual smoke: per-side face meshes selected by CharacterPartSlot.
-- Run with the current v2 client modules in Studio Command Bar.
local client=nil
for _,object in game.StarterPlayer.StarterPlayerScripts:GetChildren() do
    if object.Name=="Game1Client" and object:IsA("LocalScript") then client=object end
end
assert(client,"Game1Client source missing")
local modules=client.character.animation:Clone()
modules.Name="split_face_test_modules"
modules.Parent=game.ServerStorage
local Presenter=require(modules.FacePresentation)
local model=Instance.new("Model")
model.Name="split_face_fixture"
local presentation=nil
local ok,result=xpcall(function()
    local carrier=Instance.new("Part")
    carrier.Name="rig_carrier";carrier.Anchored=true;carrier.Parent=model
    local head=Instance.new("Bone");head.Name="face_head";head.Parent=carrier
    local function bone(name,x)
        local b=Instance.new("Bone");b.Name=name;b.CFrame=CFrame.new(x,1,0);b.Parent=head
        return b
    end
    local left=bone("face_eye_l",-.3)
    local right=bone("face_eye_r",.3)
    bone("face_brow_r",.3)
    local originals={}
    local function part(name,slot,at)
        local mesh=Instance.new("MeshPart")
        mesh.Name=name;mesh.Size=Vector3.new(.25,.2,.06);mesh.CFrame=at
        mesh.Anchored=true;mesh.Parent=model
        mesh:SetAttribute("CharacterPartSlot",slot)
        table.insert(originals,mesh)
        return mesh
    end
    part("human_male_m001_eye_l","eye_l",CFrame.new(-.3,1,0))
    part("human_male_m002_eye_r","eye_r",CFrame.new(.3,1,0))
    part("human_male_m001_eyebrow_r","eyebrow_r",CFrame.new(.3,1.2,0))
    model.Parent=workspace
    presentation=assert(Presenter.new(model),"split face presenter did not bind")
    assert(presentation.entries.eye_l and presentation.entries.eye_r and presentation.entries.eyebrow_r,
        "side components missing")
    for _,mesh in originals do assert(mesh.LocalTransparencyModifier==1,"original not locally hidden") end
    presentation:Event({name="blink",parameters={duration=.16,side="both"}},0,0)
    local minimum=math.huge
    for _=1,8 do
        presentation:BeforeAnimation()
        presentation:Step(.02,true)
        minimum=math.min(minimum,presentation.entries.eye_l.mesh.Size.Y)
    end
    assert(minimum<.025,"per-side blink did not close")
    presentation:SetIdlePhase(1.333333)
    presentation:BeforeAnimation()
    presentation:Step(.02,true)
    assert(left.Transform.Position.Magnitude>.001 and right.Transform.Position.Magnitude>.001,
        "split-eye idle gaze was lost")
    presentation:SetIdlePhase(nil)
    presentation:BeforeAnimation()
    presentation:Step(.2,true)
    assert(presentation.entries.eye_r.mesh.Size.Y>.19,"right eye did not reopen")
    presentation:Destroy();presentation=nil
    for _,mesh in originals do assert(mesh.LocalTransparencyModifier==0,"visibility not restored") end
    assert(left.Transform==CFrame.identity and right.Transform==CFrame.identity,
        "procedural control transforms remained")
    return {ok=true,blinkMinimum=minimum,splitMeshCount=#originals}
end,debug.traceback)
if presentation then presentation:Destroy() end
model:Destroy();modules:Destroy()
assert(ok,result)
return result

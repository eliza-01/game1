-- Real controller functions + terminal policy, with fake Roblox tracks and time.
local now=0
os.clock=function() return now end
table.freeze=function(t) return t end
Enum={AnimationPriority={Action4=4}}
local DeathAnimationPolicy=dofile(arg[1])
local events={}
local function record(s) events[#events+1]=s end
local function track(name,length)
    local t={Name=name,Length=length,Speed=1,TimePosition=0,IsPlaying=false,Looped=false,
        Animation={AnimationId=name},Priority=1}
    function t:Play(fade,weight,speed) self.IsPlaying=true;self.Speed=speed;self.TimePosition=0;record('play:'..name..':'..fade) end
    function t:Stop(fade) self.IsPlaying=false;record('stop:'..name..':'..fade) end
    function t:AdjustWeight(weight,fade) self.Weight=weight end
    function t:AdjustSpeed(speed) self.Speed=speed end
    return t
end
local revive=track('revive',0)
local death=track('death',2)
local idle=track('idle',0)
local tracks={revive=revive,death=death,idle=idle}
local function model(state)
    local attrs={LifeState=state}
    return {Parent=true,attrs=attrs,GetAttribute=function(self,k)return attrs[k] end,SetAttribute=function(self,k,v)attrs[k]=v end}
end
local descriptor={}
for name in pairs(tracks) do descriptor[name]={animationId=name,clipId=name,looped=name=='idle'} end
local sent={}
local remotes={}
for _,name in ipairs({'DeathTerminalReached','ReviveAnimationFinished'}) do
    remotes[name]={IsA=function()return true end,FireServer=function(_,m,ok) sent[#sent+1]={name,m,ok} end}
end
function remotes:FindFirstChild(n)return self[n] end
local env=setmetatable({DeathAnimationPolicy=DeathAnimationPolicy,
    ReplicatedStorage={FindFirstChild=function()return remotes end},
    AnimationResolver={Resolve=function(_,_,_,slot)return descriptor[slot] end,ResolveLocomotion=function(_,slot)return descriptor[slot] end,ListForCharacter=function()return {} end},
    animationPlaybackScale=function()return 1 end,publishPlaybackPercent=function()end,
    applyBackwardPlayback=function()end,movementSlot=function()return 'idle' end,
    disconnectJumpStart=function()end, warn=function(s)record('warn')end,
    task={spawn=function(fn)fn()end}, LIFE_LOAD_SECONDS=8, RETRY_SECONDS=.25,
}, {__index=_G})
env.cacheObject={Get=function(_,d)return tracks[d.clipId]end,IsLoaded=function(_,t)return t and t.Length>.01 end,Prewarm=function()return {ready=0,total=0,elapsed=0}end}
env.findAnimator=function()return env.available and {} or nil end
env.AnimationTrackCache={new=function()return env.cacheObject end}
env.stopCurrentLoop=function(fade)if env.currentLoop then env.currentLoop:Stop(fade)end end
env.stopCurrentAction=function(fade)
    if env.currentAction==env.reviveTrack then env.reviveTrack=nil end
    if env.currentAction==env.deathTrack then env.deathTrack=nil end
    if env.currentAction and env.currentAction.IsPlaying then env.currentAction:Stop(fade) end
end
local code=assert(io.open(arg[2])):read('*a')
local functions=assert(load(code..'\nreturn {handle=handleLifeState,step=maintainDeathPose,refresh=refreshLoop}', 'controller', 't', env))()
local function reset(state)
    env.character=model(state);env.cache=nil;env.animator=nil;env.available=false;env.lifeTransition=false;env.lastLifeState='Alive'
    env.lifeRequest=nil;env.currentAction=nil;env.currentActionSlot='';env.currentActionComposed=false
    env.currentLoop=nil;env.currentLoopClipId='';env.deathTrack=nil;env.reviveTrack=nil;env.deathTerminalPoseHeld=false;env.deathTerminalReported=false;env.reviveTerminalPoseHeld=false
    env.revealAfterEvaluation=false;env.awaitingRevivePose=false;env.reviveReportPending=false;env.nextAnimatorProbe=0;env.nextLoopProbe=0;env.loopPending=false;env.airborneSequence=-1
    env.attackLowerBodyActive=false;now=0;events={};sent={}
    revive.Length=0;revive.IsPlaying=false;idle.Length=0;idle.IsPlaying=false;death.IsPlaying=false
    functions.handle()
end
local function step(t,delta) now=t;functions.step(delta or .016)end
reset('Reviving')
step(0);assert(not env.cache and not revive.IsPlaying and #sent==0)
env.available=true;step(.25);assert(env.cache and not revive.IsPlaying and #sent==0)
revive.Length=2;step(.5);assert(revive.IsPlaying and revive.Priority==4 and not env.character.attrs.RevivePoseReady)
step(.52);assert(env.character.attrs.RevivePoseReady==true)
revive.TimePosition=1.975;step(2.48,.02);assert(revive.IsPlaying and revive.Speed==0 and revive.Looped and #sent==1 and sent[1][2]==env.character and sent[1][3]==true)
step(5);assert(revive.IsPlaying and #sent==1) -- delayed server acknowledgement
-- Alive arrives while locomotion still cold: hold remains at full weight.
env.character.attrs.LifeState='Alive';functions.handle();assert(revive.IsPlaying and not idle.IsPlaying)
idle.Length=1;step(5.3);assert(idle.IsPlaying and not revive.IsPlaying)
assert(events[#events-1]=='play:idle:0' and events[#events]=='stop:revive:0.1')
-- Missing revive: explicit degraded notification; no invented completion/pose.
reset('Reviving');step(0);step(8.1);assert(#sent==1 and sent[1][3]==false and not env.character.attrs.RevivePoseReady)
env.character.attrs.LifeState='Alive';functions.handle();env.available=true;idle.Length=1;step(8.4);step(8.5);assert(idle.IsPlaying and env.character.attrs.RevivePoseReady)
-- Existing locomotion remains until Death is ready. Missing Death never forges terminal ACK.
reset('Alive');env.available=true;idle.Length=1;step(.3);assert(idle.IsPlaying)
death.Length=0;env.character.attrs.LifeState='Dying';functions.handle();step(1);step(9.2);assert(idle.IsPlaying and #sent==0)
death.Length=2;step(9.5);assert(death.IsPlaying and not idle.IsPlaying)
death.TimePosition=1.99;step(11.5);assert(death.IsPlaying and death.Speed==0 and #sent==1 and sent[1][1]=='DeathTerminalReached')
step(12);assert(#sent==1)
print('M654 Lua transitions: delayed Animator/Length/Alive, failure, death retry, full-weight handoff OK')

-- Exceptional home return. No new monster, respawn, healing or navigation.
-- The AI owns the encounter; this module owns only the bounded recall sequence.
local Players=game:GetService("Players")
local ReplicatedStorage=game:GetService("ReplicatedStorage")
local TweenService=game:GetService("TweenService")
local Trace=require(script.Parent:WaitForChild("MonsterNavigationTrace"))
local Recall={}
local FADE_SECONDS=1.05
local FX_RADIUS=160
local remote

function Recall.Start()
    if remote then return end
    local remotes=ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not remotes then
        remotes=Instance.new("Folder"); remotes.Name="Game1Remotes"; remotes.Parent=ReplicatedStorage
    end
    remote=Instance.new("RemoteEvent"); remote.Name="MonsterHomeRecallVisual"; remote.Parent=remotes
end

local function publish(agent)
    local collider=agent.model:FindFirstChild("RootCollider")
    if not collider or not collider:IsA("BasePart") then return end
    local foot=collider.Position-Vector3.yAxis*(collider.Size.Y/2)
    local height=math.max(10.4,collider.Size.Y+3)
    local radius=math.max(1.7,math.max(collider.Size.X,collider.Size.Z)/2+.4)
    for _,player in ipairs(Players:GetPlayers()) do
        local root=player.Character and player.Character:FindFirstChild("HumanoidRootPart")
        if root and root:IsA("BasePart") and (root.Position-foot).Magnitude<=FX_RADIUS then
            remote:FireClient(player,foot,height,radius)
        end
    end
end

local function fade(state,hidden)
    for _,item in ipairs(state.alpha) do
        if item.tween then item.tween:Cancel(); item.tween:Destroy(); item.tween=nil end
        if item.instance.Parent then
            local tween=TweenService:Create(item.instance,TweenInfo.new(FADE_SECONDS,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut),
                {Transparency=hidden and 1 or item.original})
            item.tween=tween; tween:Play()
        end
    end
end
local function zeroMotion(root)
    root.AssemblyLinearVelocity=Vector3.zero
    root.AssemblyAngularVelocity=Vector3.zero
end
function Recall.Active(agent)
    return agent.homeRecall~=nil
end
function Recall.Begin(agent)
    if Recall.Active(agent) then return end
    local root,model=agent.root,agent.model
    local state={alpha={},phase="Out",untilTime=os.clock()+FADE_SECONDS,anchored=root.Anchored,
        damageable=model:GetAttribute("Damageable")}
    agent.homeRecall=state
    model:SetAttribute("MonsterHomeRecalling",true)
    model:SetAttribute("Damageable",false)
    agent.humanoid:Move(Vector3.zero,false)
    agent.humanoid:MoveTo(root.Position)
    root.Anchored=true; zeroMotion(root)
    for _,instance in ipairs(model:GetDescendants()) do
        if (instance:IsA("BasePart") or instance:IsA("Decal") or instance:IsA("Texture")) and instance.Transparency<1 then
            table.insert(state.alpha,{instance=instance,original=instance.Transparency})
        end
    end
    publish(agent); fade(state,true)
    Trace.Event(agent,"HOME_RECALL_OUT")
end
function Recall.Cancel(agent)
    local state=agent.homeRecall
    if not state then return end
    agent.homeRecall=nil
    for _,item in ipairs(state.alpha) do
        if item.tween then item.tween:Cancel(); item.tween:Destroy() end
        if item.instance.Parent then item.instance.Transparency=item.original end
    end
    local alive=agent.model:GetAttribute("LifeState")=="Alive"
    if agent.root.Parent and alive then
        zeroMotion(agent.root)
        agent.root.Anchored=state.anchored
        if not state.anchored then
            local ok,err=pcall(function() agent.root:SetNetworkOwner(nil) end)
            if not ok then warn("[game1][monster-recall] network ownership: "..tostring(err)) end
        end
    end
    if agent.model.Parent then
        if alive then agent.model:SetAttribute("Damageable",state.damageable) end
        agent.model:SetAttribute("MonsterHomeRecalling",nil)
    end
end
function Recall.Step(agent)
    local state=agent.homeRecall
    if not state or os.clock()<state.untilTime then return false end
    if state.phase=="Out" then
        for _,item in ipairs(state.alpha) do
            if item.tween then item.tween:Cancel(); item.tween:Destroy(); item.tween=nil end
            if item.instance.Parent then item.instance.Transparency=1 end
        end
        local root=agent.root
        -- Move the whole assembly by the navigation-root delta, preserving yaw.
        agent.model:PivotTo(agent.model:GetPivot()+(agent.home-root.Position))
        zeroMotion(root)
        state.phase="In"; state.untilTime=os.clock()+FADE_SECONDS
        publish(agent); fade(state,false)
        Trace.Event(agent,"HOME_RECALL_IN")
        return false
    end
    Recall.Cancel(agent)
    Trace.Event(agent,"HOME_RECALL_DONE")
    return true
end
return table.freeze(Recall)

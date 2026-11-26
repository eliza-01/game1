--!strict
-- Local payment presentation only; a successful server purchase is the trigger.
local RunService=game:GetService("RunService")
local Coins={}
function Coins.Play(character: Model, npc: Model, amount: number)
    local root=character:FindFirstChild("RootCollider")
    local torso=npc:FindFirstChild("Torso")
    if not root or not root:IsA("BasePart") or not torso or not torso:IsA("BasePart") then return end
    local folder=Instance.new("Folder"); folder.Name="BufferPaymentVisual"; folder.Parent=workspace
    local origin=root.Position+Vector3.new(0,1.3,0)
    local pieces={}
    for i=1,amount do
        local coin=Instance.new("Part"); coin.Name="Coin"; coin.Shape=Enum.PartType.Cylinder
        coin.Size=Vector3.new(.10,.48,.48); coin.Material=Enum.Material.Metal; coin.Color=Color3.fromRGB(255,195,49)
        coin.Anchored=true; coin.CanCollide=false; coin.CanTouch=false; coin.CanQuery=false; coin.CastShadow=false
        coin.CFrame=CFrame.new(origin); coin.Parent=folder; pieces[i]=coin
    end
    local began=os.clock()
    local connection: RBXScriptConnection?=nil
    local finished=false
    local function finish()
        if finished then return end
        finished=true
        if connection then connection:Disconnect(); connection=nil end
        folder:Destroy()
    end
    connection=RunService.Heartbeat:Connect(function()
        if not character.Parent or not npc.Parent or not torso.Parent then finish(); return end
        local t=math.clamp((os.clock()-began)/.65,0,1)
        local target=torso.Position
        for i,coin in ipairs(pieces) do
            local angle=2*math.pi*(i-1)/#pieces
            local spread=Vector3.new(math.cos(angle)*.95,math.sin(angle)*.7,math.sin(angle)*.95)*math.sin(math.pi*t)
            local point=origin:Lerp(target,t)+Vector3.new(0,2.5*math.sin(math.pi*t),0)+spread
            coin.CFrame=CFrame.new(point)*CFrame.Angles(t*10+angle,t*13+angle,t*5)
            coin.Transparency=math.clamp((t-.85)/.15,0,1)
        end
        if t>=1 then finish() end
    end)
    task.delay(1.5,finish)
end
return table.freeze(Coins)

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local InsertService = game:GetService("InsertService")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterConfig = require(Shared:WaitForChild("CharacterConfig"))
local CharacterMovementConfig = require(Shared:WaitForChild("CharacterMovementConfig"))
local CharacterRegistry = require(Shared:WaitForChild("CharacterRegistry"))
local BootstrapConfig = require(Shared:WaitForChild("BootstrapConfig"))
local CharacterStatsService = require(script.Parent:WaitForChild("CharacterStatsService"))
local Service = {}
local started = false
local cache = ServerStorage:FindFirstChild("game1CharacterCache") or Instance.new("Folder")
cache.Name = "game1CharacterCache"; cache.Parent = ServerStorage

local function findArchetype(archetypeId: string?): any?
    if not archetypeId or archetypeId == "" then return nil end
    for _, row in ipairs(CharacterRegistry.archetypes or {}) do
        if tostring(row.id) == archetypeId then return row end
    end
    return nil
end
local function registeredAssetId(row: any?): number?
    if not row then return nil end
    if type(row.model) == "table" then return tonumber(row.model.assetId) end
    return tonumber(row.modelAssetId) -- m1 compatibility during live sync
end
local function selectedAsset(): (number?, string, string, string?)
    local requestedId = tostring(CharacterRegistry.activeArchetypeId or "")
    local row = findArchetype(requestedId)
    local id = registeredAssetId(row)
    if row and id then
        return id, tostring(row.id), tostring(row.displayName or row.id), requestedId
    end
    return tonumber(BootstrapConfig.CharacterModelAssetId), "bootstrap", BootstrapConfig.CharacterLabel, requestedId ~= "" and requestedId or nil
end
local function getTemplate(assetId: number): Model?
    local key = tostring(assetId)
    local cached = cache:FindFirstChild(key)
    if cached and cached:IsA("Model") then return cached end
    local ok, bundle = pcall(InsertService.LoadAsset, InsertService, assetId)
    if not ok or not bundle then warn("[game1] Cannot load character asset", assetId, bundle); return nil end
    local model = bundle:FindFirstChildWhichIsA("Model", true)
    if not model then bundle:Destroy(); warn("[game1] Asset contains no Model", assetId); return nil end
    local template = model:Clone(); template.Name = key; template.Parent = cache; bundle:Destroy(); return template
end
local function prepareVisual(visual: Model): BasePart?
    for _, object in visual:GetDescendants() do
        if object:IsA("Humanoid") then object:Destroy()
        elseif object:IsA("BasePart") then object.Anchored=false; object.CanCollide=false; object.CanTouch=false; object.CanQuery=false; object.Massless=true end
    end
    local host = visual:FindFirstChildOfClass("AnimationController") or visual:FindFirstChildWhichIsA("AnimationController", true)
    if not host then host=Instance.new("AnimationController"); host.Name="AnimationController"; host.Parent=visual end
    if not host:FindFirstChildOfClass("Animator") then local a=Instance.new("Animator"); a.Parent=host end
    local root = visual:FindFirstChild("RootPart", true)
    if root and root:IsA("BasePart") then return root end
    return visual:FindFirstChildWhichIsA("BasePart", true)
end
local function spawnCFrame(player: Player): CFrame
    local s = player.RespawnLocation
    if not (s and s.Enabled) then for _, x in Workspace:GetDescendants() do if x:IsA("SpawnLocation") and x.Enabled then s=x; break end end end
    if s then local p=s.Position+Vector3.new(0,s.Size.Y*.5+CharacterConfig.RootAnchorOffset,0); local _,y,_=s.CFrame:ToOrientation(); return CFrame.new(p)*CFrame.Angles(0,y,0) end
    return CFrame.new(0, CharacterConfig.RootAnchorOffset+8, 0)
end
local function createRoot(character, cf)
    local r=Instance.new("Part"); r.Name="RootCollider"; r.Size=CharacterConfig.RootColliderSize; r.CFrame=cf; r.Transparency=1; r.Anchored=false; r.CanCollide=false; r.CanTouch=false; r.CanQuery=true; r.Massless=true; r.Parent=character; character.PrimaryPart=r; return r
end
local function createNavigation(character, root)
    local n=Instance.new("Part"); n.Name="NavigationRoot"; n.Size=CharacterConfig.NavigationRootSize; n.CFrame=root.CFrame+Vector3.new(0,CharacterConfig.NavigationCenterOffset-CharacterConfig.RootAnchorOffset,0); n.Transparency=1; n.Anchored=false; n.CanCollide=true; n.CanTouch=false; n.CanQuery=false; n.Parent=character
    local weld=Instance.new("WeldConstraint"); weld.Part0=n; weld.Part1=root; weld.Parent=n
    return n
end
local function createController(character, nav)
    local m=Instance.new("ControllerManager"); m.Name="ControllerManager"; m.RootPart=nav; m.BaseMoveSpeed=CharacterMovementConfig.DefaultRunSpeed; m.BaseTurnSpeed=CharacterConfig.TurnSpeed; m.UpDirection=Vector3.yAxis; m.MovingDirection=Vector3.zero; m.FacingDirection=nav.CFrame.LookVector; m.Parent=character
    local g=Instance.new("GroundController"); g.Name="GroundController"; g.GroundOffset=CharacterConfig.GroundOffset; g.AccelerationTime=.08; g.DecelerationTime=.08; g.Friction=2; g.FrictionWeight=100; g.Parent=m
    local a=Instance.new("AirController"); a.Name="AirController"; a.MaintainAngularMomentum=false; a.MaintainLinearMomentum=true; a.Parent=m
    local p=Instance.new("Part"); p.Name="GroundSensorPart"; p.Size=nav.Size; p.CFrame=nav.CFrame; p.Transparency=1; p.CanCollide=false; p.CanQuery=false; p.CanTouch=false; p.Massless=true; p.Parent=character
    local w=Instance.new("WeldConstraint"); w.Part0=nav; w.Part1=p; w.Parent=nav
    m.ActiveController=g
    return m,p
end
local function createSensor(manager, part)
    local s=Instance.new("ControllerPartSensor"); s.Name="GroundSensor"; s.SensorMode=Enum.SensorMode.Floor; s.SearchDistance=CharacterConfig.GroundSearchDistance; s.Parent=part; manager.GroundSensor=s
end
local function floorY(character, root)
    local params=RaycastParams.new(); params.FilterType=Enum.RaycastFilterType.Exclude; params.FilterDescendantsInstances={character}; params.RespectCanCollide=true
    local hit=Workspace:Raycast(root.Position,Vector3.new(0,-(CharacterConfig.GroundSearchDistance+5),0),params)
    return hit and hit.Position.Y or root.Position.Y-CharacterConfig.RootAnchorOffset
end
local function attachVisual(character, root, template)
    local visual=template:Clone(); visual.Name="Visual"; visual.Parent=character
    local vr=prepareVisual(visual); if not vr then visual:Destroy(); return false end
    vr.Size=CharacterConfig.VisualRootAnchorSize
    local fy=floorY(character,root); local _,yaw,_=root.CFrame:ToOrientation(); local rot=visual:GetPivot().Rotation
    visual:PivotTo(CFrame.new(root.Position.X,fy,root.Position.Z)*CFrame.Angles(0,yaw,0)*rot)
    visual:PivotTo(visual:GetPivot() + (Vector3.new(root.Position.X,fy+CharacterConfig.VisualGroundClearance,root.Position.Z)-vr.Position))
    local weld=Instance.new("WeldConstraint"); weld.Name="VisualRootWeld"; weld.Part0=root; weld.Part1=vr; weld.Parent=root
    return true
end
local function spawn(player)
    if player.Character then player.Character:Destroy() end
    local assetId, archetype, label, requestedArchetype = selectedAsset(); if not assetId then return end
    local template=getTemplate(assetId); if not template then return end
    local c=Instance.new("Model"); c.Name=player.Name; c:SetAttribute("CharacterArchetype",archetype); c:SetAttribute("CharacterDisplayName",label); c:SetAttribute("RequestedCharacterArchetype",requestedArchetype or ""); c:SetAttribute("UsingBootstrapVisual",archetype=="bootstrap"); c:SetAttribute("CharacterOwnerUserId",player.UserId); c:SetAttribute("CustomCharacter",true); c:SetAttribute("MoveSpeed",CharacterMovementConfig.DefaultRunSpeed); c:SetAttribute("AnimationMovementMode","Run"); c:SetAttribute("AnimationMovementDirection","Forward"); c:SetAttribute("MovementState","Idle")
    CharacterStatsService.Initialize(c)
    local root=createRoot(c,spawnCFrame(player)); local nav=createNavigation(c,root); local manager,sensorPart=createController(c,nav)
    if not attachVisual(c,root,template) then c:Destroy(); return end
    c.Parent=Workspace; createSensor(manager,sensorPart); player.Character=c
    pcall(function() nav:SetNetworkOwner(player) end)
    c:GetAttributeChangedSignal("LifeState"):Connect(function()
        if c:GetAttribute("LifeState") ~= "Dead" then return end
        manager.MovingDirection=Vector3.zero; nav.AssemblyLinearVelocity=Vector3.zero; pcall(function() nav:SetNetworkOwner(nil) end); nav.Anchored=true
        task.delay(3,function() if player.Parent==Players and player.Character==c then spawn(player) end end)
    end)
    print(("[game1] character ready: %s · %s · asset %d"):format(player.Name,archetype,assetId))
end
function Service.Start()
    if started then return end; started=true; Players.CharacterAutoLoads=false
    Players.PlayerAdded:Connect(function(p) task.defer(spawn,p) end)
    for _,p in Players:GetPlayers() do task.defer(spawn,p) end
end
function Service.Respawn(player) spawn(player) end
return Service

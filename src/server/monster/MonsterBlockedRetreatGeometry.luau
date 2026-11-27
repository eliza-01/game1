-- Bounded outward steps for blocked pursuit. No graph search and no teleports.
-- A separate physical query includes Terrain; the rescue-route filter is unchanged.
local Workspace=game:GetService("Workspace")
local Geometry=require(script.Parent:WaitForChild("MonsterRecoveryGeometry"))
local Retreat={}
local UP=Vector3.yAxis
local STEP=6
local ANGLES={0,45,-45,75,-75}

function Retreat.FindPoint(agent,position,target,desired,allowed)
    local away=Geometry.Horizontal(position-target)
    local distance=away.Magnitude
    local direction=distance>.01 and away.Unit or Vector3.new(1,0,0)
    local length=math.min(STEP,math.max(1.5,desired-distance))
    local params=Geometry.Params(agent)
    local excluded={}
    for _,instance in ipairs(params.FilterDescendantsInstances) do
        if instance~=Workspace.Terrain then table.insert(excluded,instance) end
    end
    params.FilterDescendantsInstances=excluded
    local foot=Geometry.Body(agent)
    local root=agent.root
    for _,degrees in ipairs(ANGLES) do
        local angle=math.rad(degrees)
        local dir=Vector3.new(direction.X*math.cos(angle)-direction.Z*math.sin(angle),0,direction.X*math.sin(angle)+direction.Z*math.cos(angle))
        local delta=dir*length
        local floor=Workspace:Raycast(foot+delta+UP*3,-UP*6,params)
        if floor then
            local middle=Workspace:Raycast(foot+delta*.5+UP*3,-UP*6,params)
            local point=position+delta+UP*(floor.Position.Y-foot.Y)
            if middle and math.abs(middle.Position.Y-foot.Y)<=3 and allowed(point)
                and Geometry.Horizontal(point-target).Magnitude>distance+.1
                and not Workspace:Blockcast(root.CFrame,root.Size*.95,point-position,params) then
                return point
            end
        end
    end
    return nil
end
return table.freeze(Retreat)

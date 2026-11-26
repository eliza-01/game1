--!strict
-- Studio graybox only. Authored landmarks in entry-local studs; lightweight
-- visual proxy parts cannot intercept combat rays or alter pathfinding.
local Decor = {}
local function part(parent: Instance, frame: CFrame, name: string, size: Vector3, x: number, y: number, z: number, color: Color3)
    local p = Instance.new("Part")
    p.Name=name; p.Size=size; p.CFrame=frame*CFrame.new(x,y,z)
    p.Color=color; p.Anchored=true; p.CanCollide=false; p.CanQuery=false; p.CanTouch=false
    p.Material=Enum.Material.SmoothPlastic; p.Parent=parent
    return p
end
local wood=Color3.fromRGB(120,86,61)
local stone=Color3.fromRGB(103,112,119)
local leaf=Color3.fromRGB(81,120,73)
local function house(parent: Instance, frame: CFrame, x: number, z: number, haunted: boolean)
    part(parent,frame,"House",Vector3.new(20,12,15),x,6,z,if haunted then stone else wood)
    part(parent,frame,"Roof",Vector3.new(24,4,19),x,14,z,if haunted then Color3.fromRGB(57,57,69) else Color3.fromRGB(139,73,49))
    part(parent,frame,"Door",Vector3.new(4,8,0.4),x,4,z+7.7,Color3.fromRGB(47,42,39))
    part(parent,frame,"Window",Vector3.new(4,4,0.4),x+6,8,z+7.7,Color3.fromRGB(196,166,91))
end
local function tree(parent: Instance, frame: CFrame, x: number,z: number,dead: boolean)
    part(parent,frame,"Trunk",Vector3.new(3,12,3),x,6,z,wood)
    if dead then
        part(parent,frame,"DeadCrown",Vector3.new(9,2,3),x,11,z,Color3.fromRGB(68,62,69))
    else
        part(parent,frame,"Crown",Vector3.new(11,9,11),x,13,z,leaf)
    end
end
local function cart(parent: Instance,frame: CFrame,x: number,z: number)
    part(parent,frame,"Cart",Vector3.new(9,3,14),x,3,z,wood)
    for _,dx in ipairs({-5,5}) do for _,dz in ipairs({-4,4}) do
        local wheel=part(parent,frame,"Wheel",Vector3.new(2,5,5),x+dx,2.5,z+dz,stone)
        wheel.Shape=Enum.PartType.Cylinder
    end end
end
local function gateway(parent: Instance, frame: CFrame, x: number,z: number, color: Color3)
    for _,dx in ipairs({-12,12}) do part(parent,frame,"Pillar",Vector3.new(5,22,5),x+dx,11,z,color) end
    part(parent,frame,"Lintel",Vector3.new(29,5,5),x,23,z,color)
end
function Decor.Build(parent: Instance, layout: any)
    local folder=Instance.new("Folder"); folder.Name="GrayboxLandmarks"; folder.Parent=parent
    for index,box in pairs(layout.boxes) do
        if index>6 then continue end
        local area=Instance.new("Folder"); area.Name="Landmarks_"..index; area.Parent=folder
        local frame=box.entryFrame
        local function p(name: string,size: Vector3,x: number,y: number,z: number,color: Color3)
            return part(area,frame,name,size,x,y,z,color)
        end
        -- Paths are visible guidance, not barriers. The actual deck stays authoritative.
        local pathColor=Color3.fromRGB(145,131,106)
        p("ArrivalPath",Vector3.new(14,0.04,176),0,0.025,88,pathColor)
        if index==1 or index==4 then p("WestPath",Vector3.new(192,0.04,14),-96,0.025,0,pathColor) end
        if index==2 or index==3 or index==4 then p("EastPath",Vector3.new(192,0.04,14),96,0.025,0,pathColor) end
        if index==1 or index==5 or index==6 then p("NorthPath",Vector3.new(14,0.04,192),0,0.025,-96,pathColor) end
        if index==1 then
            p("Stream",Vector3.new(18,0.06,100),-105,0.04,118,Color3.fromRGB(65,139,163))
            p("Bridge",Vector3.new(24,0.2,12),-105,0.16,92,wood)
            house(area,frame,34,144,false); cart(area,frame,-30,142)
            p("FlowerBed",Vector3.new(18,0.12,24),132,0.08,125,Color3.fromRGB(155,105,145))
            tree(area,frame,-150,-138,false); tree(area,frame,-154,135,false)
            gateway(area,frame*CFrame.Angles(0,math.pi/2,0),0,-177,Color3.fromRGB(64,57,75))
        elseif index==2 then
            gateway(area,frame,0,158,Color3.fromRGB(67,61,78))
            for _,x in ipairs({-36,36}) do for _,z in ipairs({130,85,38,-50,-92}) do tree(area,frame,x,z,true) end end
            house(area,frame,-95,25,true); cart(area,frame,35,110)
            p("Chapel",Vector3.new(20,20,24),-104,10,-150,stone)
        elseif index==3 then
            p("SandBank",Vector3.new(35,0.08,70),-120,0.05,120,Color3.fromRGB(171,145,101))
            gateway(area,frame,-90,20,stone); cart(area,frame,35,120)
            p("Excavation",Vector3.new(28,5,24),100,2.5,-100,stone)
        elseif index==4 then
            p("Pool",Vector3.new(45,0.08,50),100,0.06,125,Color3.fromRGB(55,142,132))
            for _,x in ipairs({-35,35}) do for _,z in ipairs({120,60,-60,-125}) do tree(area,frame,x,z,false) end end
            gateway(area,frame,-115,-145,stone)
        elseif index==5 then
            gateway(area,frame,0,150,stone)
            house(area,frame,-35,110,false); cart(area,frame,35,100)
            for _,x in ipairs({-150,150}) do p("Watchtower",Vector3.new(12,26,12),x,13,0,stone) end
            p("RitualFloor",Vector3.new(32,0.2,32),100,0.11,-148,Color3.fromRGB(155,69,59))
        else
            for _,x in ipairs({-34,34}) do p("Monolith",Vector3.new(8,25,8),x,12.5,100,stone) end
            gateway(area,frame,0,25,Color3.fromRGB(91,110,153))
            p("Altar",Vector3.new(22,4,22),0,2,-105,Color3.fromRGB(98,102,159))
        end
    end
end
return table.freeze(Decor)

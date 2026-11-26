--!strict
-- Compact graybox map. Coordinates are in the authored origin frame.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local CharacterConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local HuntingPlan = require(script.Parent:WaitForChild("GameplayWorldHuntingPlan"))
local Layout = {}
local ZONE_SIZE = 384
local GAP = 24
local PITCH = ZONE_SIZE + GAP
local HEIGHT = 16
-- Same topology as Design. The annex is not release content.
local zones = {
    {name="Солнечная долина", low=1, high=4, col=2, row=4, color=Color3.fromHex("83ad61"), gear={1,5,10}},
    {name="Безмолвный лес", low=5, high=9, col=1, row=4, color=Color3.fromHex("9b85c4"), gear={1,5,10}},
    {name="Расколотые земли", low=10, high=14, col=1, row=3, color=Color3.fromHex("c4a16f"), gear={5,10,15}},
    {name="Забытые сады", low=15, high=19, col=2, row=3, color=Color3.fromHex("45b6a0"), gear={10,15,20}},
    {name="Пепельный бастион", low=20, high=24, col=2, row=2, color=Color3.fromHex("c77659"), gear={15,20,25}},
    {name="Драконий предел", low=25, high=30, col=2, row=1, color=Color3.fromHex("789bd4"), gear={20,25,30}},
    {name="Резерв · GP", low=31, high=35, col=1, row=1, color=Color3.fromHex("7c8490"), gear={25,30,35}},
    {name="Skilled · GP", low=20, high=20, col=1, row=2, color=Color3.fromHex("a17eb7"), gear={15,20,25}, skilled=true},
}
function Layout.Build(origin: CFrame, rows: {any}, maxLevel: number, spacing: number, size: Vector3, maxGroup: number, skilledRows: {any})
    local floorY = -CharacterConfig.RootAnchorOffset
    local function frame(x: number, z: number): CFrame return origin * CFrame.new(x, floorY, z) end
    local platforms, slots, boxes, extraSlots = {}, {}, {}, {}
    local hubWidth = math.max(216, spacing * 3, maxGroup * (size.Magnitude + 2) / math.pi + 100)
    table.insert(platforms,{name="Hub",top=frame(0,0),size=Vector3.new(hubWidth,0,hubWidth),color=Color3.fromRGB(64,76,92)})
    local firstZ = -(hubWidth/2 + GAP + ZONE_SIZE/2)
    local function center(zone: any): CFrame
        return frame((zone.col-2)*PITCH, firstZ+(zone.row-4)*PITCH)
    end
    local function addBridge(name: string, a: CFrame, b: CFrame, length: number)
        local midpoint = (a.Position+b.Position)/2
        local direction = (b.Position-a.Position).Unit
        table.insert(platforms,{name=name,top=CFrame.lookAt(midpoint,midpoint+direction),size=Vector3.new(32,0,length+4),color=Color3.fromRGB(78,86,94)})
    end
    for index, zone in ipairs(zones) do
        if zone.low>maxLevel or (zone.skilled and #skilledRows==0) then continue end
        local top = center(zone)
        local entryFrame = HuntingPlan.EntryFrame(index, top)
        local box = {index=index,name=zone.name,low=zone.low,high=math.min(zone.high,maxLevel),top=top,size=Vector3.new(ZONE_SIZE,HEIGHT,ZONE_SIZE),color=zone.color,gear=zone.gear,
            entry=entryFrame*CFrame.new(0,CharacterConfig.RootAnchorOffset,ZONE_SIZE/2-24),entryFrame=entryFrame,skilled=zone.skilled}
        boxes[index]=box
        table.insert(platforms,{name="Zone_"..index,top=top,size=Vector3.new(ZONE_SIZE,0,ZONE_SIZE),color=zone.color:Lerp(Color3.fromRGB(40,46,52),0.65)})
        local selected={}
        for _, row in ipairs(if zone.skilled then skilledRows else rows) do
            if zone.skilled or (row.level>=zone.low and row.level<=zone.high) then table.insert(selected,row) end
        end
        -- Authored release pockets; reserve and Skilled remain regular calibration stands.
        local cols=if zone.skilled then math.min(4,math.max(1,#selected)) else 2
        local lines=math.max(1,math.ceil(#selected/cols))
        local points = {}
        for k,row in ipairs(selected) do
            local authored=HuntingPlan.Point(index,zone.low,row)
            local column=if zone.skilled then (k-1)%cols else (if row.type=="melee" then 0 else 1)
            local line=if zone.skilled then math.floor((k-1)/cols) else row.level-zone.low
            local x=if authored then authored.X else (column-(cols-1)/2)*(if zone.skilled then 72 else 216)
            local z=if authored then authored.Y else ((lines-1)/2-line)*(if zone.skilled then 120 else math.min(44,220/math.max(1,lines-1)))
            points[k]={row=row,x=x,z=z,point=(entryFrame*CFrame.new(x,0,z)).Position}
        end
        for _,row in ipairs(selected) do
            for _,extra in ipairs(HuntingPlan.Extra(index,zone.low,row)) do
                table.insert(points,{row=row,x=extra.X,z=extra.Y,point=(entryFrame*CFrame.new(extra.X,0,extra.Y)).Position,extra=true})
            end
        end
        for k,item in ipairs(points) do
            local row, point = item.row, item.point
            local reach=math.max(30,row.attackRange+12)
            -- Select a visit point away from neighbours, inside the deck. Facing uses that approach.
            local facing=entryFrame.ZVector
            local best=-math.huge
            for direction=0,7 do
                local angle=direction*math.pi/4
                local dx,dz=math.cos(angle),math.sin(angle)
                local x,z=item.x+dx*reach,item.z+dz*reach
                if math.max(math.abs(x),math.abs(z))>ZONE_SIZE/2-8 then continue end
                local distance=math.huge
                for otherIndex,other in ipairs(points) do
                    if otherIndex~=k then distance=math.min(distance,Vector2.new(x-other.x,z-other.z).Magnitude) end
                end
                if distance>best then
                    best=distance
                    facing=entryFrame.RightVector*dx+entryFrame.ZVector*dz
                end
            end
            local visit=point+facing*reach+Vector3.yAxis*CharacterConfig.RootAnchorOffset
            local homeRadius=math.min(75,ZONE_SIZE/2-8-math.max(math.abs(item.x),math.abs(item.z)))
            local slot={point=point,facing=facing,homeRadius=homeRadius,visit=CFrame.lookAt(visit,point+Vector3.yAxis*CharacterConfig.RootAnchorOffset),zone=index}
            if item.extra then table.insert(extraSlots,{row=row,slot=slot}) else slots[row.id]=slot end
        end
    end
    -- Main route + return shortcut. Bridges meet the actual box boundaries.
    for index=1,5 do if boxes[index] and boxes[index+1] then addBridge("Road_"..index,boxes[index].top,boxes[index+1].top,GAP) end end
    if boxes[1] and boxes[4] then addBridge("ReturnRoad",boxes[1].top,boxes[4].top,GAP) end
    if boxes[1] then
        local hubEdge=frame(0,-hubWidth/2)
        local zoneEdge=boxes[1].top*CFrame.new(0,0,ZONE_SIZE/2)
        addBridge("HubRoad",hubEdge,zoneEdge,GAP)
    end
    return {slots=slots,extraSlots=extraSlots,platforms=platforms,boxes=boxes,hubWidth=hubWidth,zoneSize=ZONE_SIZE,hub=origin,weaponOrigin=origin*CFrame.new(-15,0,-60)}
end
return table.freeze(Layout)

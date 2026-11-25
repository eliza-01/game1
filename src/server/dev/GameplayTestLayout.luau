--!strict
-- Pure geometry in the authored origin frame. No spawning or AI state.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local CharacterConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local Layout = {}
function Layout.Build(origin: CFrame, rows: {any}, maxLevel: number, spacing: number, size: Vector3, maxGroup: number, skilledRows: {any})
    local columns = math.ceil(maxLevel / 2)
    local groupMargin = math.max(12, math.max(size.X, size.Z) / 2 + 4, math.ceil(maxGroup * (math.max(size.X, size.Z) + 2) / (2 * math.pi)) + 4)
    local width = (columns - 1) * spacing + 2 * groupMargin
    local centerX = (columns - 1) * spacing / 2
    local floorY = -CharacterConfig.RootAnchorOffset
    local trackWidth = 12
    local meleeGap = math.max(16, spacing / 2)
    local hubHalf = math.max(44, groupMargin + 8)
    local meleeTrackZ = -(hubHalf + 40 + groupMargin + meleeGap)
    local maxRange = 0
    for _, row in ipairs(rows) do if row.type == "ranged" then maxRange = math.max(maxRange, row.attackRange) end end
    local rangedTrackZ = meleeTrackZ - meleeGap - groupMargin * 2 - maxRange - trackWidth / 2 - 32
    local function frame(x: number, z: number): CFrame
        return origin * CFrame.new(x, floorY, z)
    end
    local tracks = {
        {name="MeleeSprintTrack", top=frame(centerX, meleeTrackZ), size=Vector3.new(width, 0, trackWidth)},
        {name="RangedSprintTrack", top=frame(centerX, rangedTrackZ), size=Vector3.new(width, 0, trackWidth)},
    }
    local slots = {}
    for _, row in ipairs(rows) do
        local side = if row.level <= columns then 1 else -1
        local column = (row.level - 1) % columns
        local x = column * spacing
        local ranged = row.type == "ranged"
        local trackZ = if ranged then rangedTrackZ else meleeTrackZ
        local offset = if ranged then trackWidth / 2 + row.attackRange else meleeGap
        local z = trackZ + side * offset
        local approachFrame: CFrame? = nil
        local approachSize: Vector3? = nil
        if ranged then
            approachFrame = frame(x, trackZ + side * (trackWidth / 2 + row.attackRange / 2))
            approachSize = Vector3.new(math.min(10, spacing - 4), 0, row.attackRange)
        end
        local visitDistance = if ranged then row.attackRange * 0.75 else math.min(5, meleeGap - trackWidth / 2 - 1)
        local visit = frame(x, z - side * visitDistance)
        local point = frame(x, z).Position
        local facing = origin.LookVector * side
        slots[row.id] = {point=point, facing=facing, approachFrame=approachFrame, approachSize=approachSize,
            visit=CFrame.lookAt(visit.Position + Vector3.new(0, CharacterConfig.RootAnchorOffset, 0), point + Vector3.new(0, CharacterConfig.RootAnchorOffset, 0))}
    end
    local meleeHalf = meleeGap + groupMargin
    local rangedHalf = trackWidth / 2 + maxRange + groupMargin
    local hubWidth = groupMargin*2 + 104
    local westX = -groupMargin - 12
    local farZ = rangedTrackZ
    local platforms = {
        {name="Hub", top=frame(-36,0), size=Vector3.new(hubWidth,0,hubHalf*2), color=Color3.fromRGB(64,76,92)},
        {name="Melee", top=frame(centerX,meleeTrackZ), size=Vector3.new(width,0,meleeHalf*2), color=Color3.fromRGB(81,71,65)},
        {name="Ranged", top=frame(centerX,rangedTrackZ), size=Vector3.new(width,0,rangedHalf*2), color=Color3.fromRGB(55,72,87)},
        {name="Connector", top=frame(westX,(farZ-hubHalf)/2), size=Vector3.new(24,0,-farZ-hubHalf), color=Color3.fromRGB(68,79,86)},
    }
    local signs = {{name="HUB / GROUP", point=frame(0, 12)}, {name="MELEE / RANGED",point=frame(westX,-hubHalf+4)}, {name="MELEE", point=frame(westX,meleeTrackZ)}, {name="RANGED", point=frame(westX,rangedTrackZ)}}
    if #skilledRows > 0 then
        local cell = math.max(spacing, 2 * (math.max(maxRange,meleeGap) + groupMargin + 8))
        local gap = 16
        local pitch = cell + gap
        local cols = math.min(6,#skilledRows)
        local z0 = hubHalf + cell/2 + 32
        for index, row in ipairs(skilledRows) do
            local x = (index-1)%cols*pitch
            local z = z0 + math.floor((index-1)/cols)*pitch
            local reach = if row.type == "ranged" then row.attackRange else meleeGap
            local point = frame(x,z).Position
            local visit = frame(x,z-reach*0.75)
            slots[row.id] = {point=point, facing=origin.LookVector, homeRadius=math.min(150,cell/2-8), visit=CFrame.lookAt(visit.Position+Vector3.yAxis*CharacterConfig.RootAnchorOffset,point+Vector3.yAxis*CharacterConfig.RootAnchorOffset),
                approachFrame=if row.type=="ranged" then frame(x,z-reach/2) else nil, approachSize=if row.type=="ranged" then Vector3.new(10,0,reach) else nil}
            table.insert(platforms,{name=row.id,top=frame(x,z),size=Vector3.new(cell,0,cell),color=Color3.fromRGB(88,67,102)})
            if (index-1)%cols > 0 then
                table.insert(platforms,{name="SkillBridgeH_"..index,top=frame(x-pitch/2,z),size=Vector3.new(gap,0,16),color=Color3.fromRGB(88,67,102)})
            end
            if index>cols then
                table.insert(platforms,{name="SkillBridgeV_"..index,top=frame(x,z-pitch/2),size=Vector3.new(16,0,gap),color=Color3.fromRGB(88,67,102)})
            end
        end
        table.insert(platforms,{name="SkillsBridge",top=frame(0,hubHalf+16),size=Vector3.new(16,0,32),color=Color3.fromRGB(88,67,102)})
        table.insert(signs,{name="SKILLED MONSTERS",point=frame(0,hubHalf)})
    end
    return {slots=slots, tracks=tracks, platforms=platforms, signs=signs, weaponOrigin=origin*CFrame.new(-groupMargin,0,0)}
end
return table.freeze(Layout)

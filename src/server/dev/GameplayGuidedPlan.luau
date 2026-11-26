--!strict
-- Immutable trial matrix. Every trial begins with fresh HP and zero test buffs.
local Balance = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("balance"):WaitForChild("Balance"))
local Plan={}
local function weaponAt(kind: string, level: number): any
    local best=nil
    for _,row in ipairs(Balance.Weapons) do
        if row.type==kind and row.level<=level and (not best or row.level>best.level) then best=row end
    end
    return assert(best)
end
local function armorAt(level: number): any
    local best=nil
    for _,row in ipairs(Balance.Armors) do if row.level<=level and (not best or row.level>best.level) then best=row end end
    return assert(best)
end
local function stage(kind: string, level: number, monster: any, repeatIndex: number): any
    local weapon=weaponAt(kind,level); local armor=armorAt(level)
    local names={}; local skillDefinitions={}
    for _,assignment in ipairs(monster.skills or {}) do
        local skill=assert(Balance.Skill(assignment.skillId)); table.insert(names,skill.name); table.insert(skillDefinitions,skill)
    end
    local description=if #names>0 then table.concat(names," + ") else monster.type
    return {label=("%s · %s · LVL %d · #%d"):format(kind,description,level,repeatIndex),weaponType=kind,level=level,
        weapon=weapon.id,armor=armor.id,monsterId=monster.id,monsterType=monster.type,repeatIndex=repeatIndex,
        upgrade=0,regen=0,vampiric=0,critPercent=0,critFlat=0,critMultiplier=Balance.Rules.critMultiplier,count=1,distance=36,skillAssignments=monster.skills,skillDefinitions=skillDefinitions,skillFactor=monster.factor}
end
function Plan.Build(): {any}
    local stages={}
    for _,kind in ipairs({"sword","dagger","bigsword","bow","dualswords"}) do
        for _,monsterType in ipairs({"melee","ranged"}) do
            for i=1,3 do table.insert(stages,stage(kind,30,assert(Balance.MonsterAt(30,monsterType)),i)) end
        end
    end
    if Balance.Test.skilledEnabled then
        local controls={}
        for _,monster in ipairs(Balance.SkilledMonsters) do
            local key=monster.type..":"..monster.level
            if monster.level~=30 and not controls[key] then
                controls[key]=true
                for i=1,3 do table.insert(stages,stage("sword",monster.level,assert(Balance.MonsterAt(monster.level,monster.type)),i)) end
            end
            table.insert(stages,stage("sword",monster.level,monster,1))
        end
    end
    return stages
end
return table.freeze(Plan)

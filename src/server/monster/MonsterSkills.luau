--!strict
-- Selects a skill and owns its cooldown/trigger history. Never applies it on a basic hit.
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance=require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Effects=require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("SkillEffects"))
local Skills={}
local states=setmetatable({}, {__mode="k"})
local function assignments(model: Model): any
    if model:GetAttribute("Game1GameplayTestOwner")==nil then return nil end
    local row=Balance.Monster(tostring(model:GetAttribute("MonsterBalanceId") or ""))
    return row and row.skills
end
local function state(model: Model): any
    local s=states[model]
    if not s then s={cooldowns={},consumed={},attacked=0}; states[model]=s end
    return s
end
function Skills.MarkAttacked(model: Model)
    if assignments(model) then local s=state(model); s.attacked+=1 end
end
function Skills.Choose(model: Model,target: Model,canDebuff: boolean): (any?, any?)
    local assigned=assignments(model)
    if not assigned or not Effects.CanCast(model) then return nil,nil end
    local s=state(model); local now=os.clock()
    for _,a in ipairs(assigned) do
        local skill=Balance.Skill(a.skillId)
        if not skill or now<(s.cooldowns[skill.id] or 0) then continue end
        local hp=tonumber(model:GetAttribute("HP")) or 0
        local maxHP=math.max(1,tonumber(model:GetAttribute("MaxHP")) or 1)
        local victim=if a.trigger=="cast" then target else model
        local ready=(a.trigger=="cast" and canDebuff)
            or (a.trigger=="attacked" and s.attacked>(s.consumed[skill.id] or 0))
            or (a.trigger=="hpBelow" and hp*100/maxHP<a.hpBelow)
            or a.trigger=="expired"
        if ready and not Effects.IsActive(victim,skill.effect) then return skill,victim end
    end
    return nil,nil
end
function Skills.Reserve(model: Model,skill: any)
    local s=state(model); s.cooldowns[skill.id]=os.clock()+skill.cooldown; s.consumed[skill.id]=s.attacked
end
return table.freeze(Skills)

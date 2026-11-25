--!strict
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Effects = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("SkillEffects"))
local Skills = {}
local cooldowns = setmetatable({}, {__mode="k"})
local function assignments(model: Model): any
    if model:GetAttribute("Game1GameplayTestOwner") == nil then return nil end
    local row = Balance.Monster(tostring(model:GetAttribute("MonsterBalanceId") or ""))
    return row and row.skills
end
local function tryCast(model: Model,target: Model,skill: any): boolean
    if not Effects.CanCast(model) then return false end
    local now = os.clock()
    local state = cooldowns[model]
    if not state then state={}; cooldowns[model]=state end
    if now < (state[skill.id] or 0) then return false end
    local power = tonumber(model:GetAttribute("Damage")) or 0
    if not Effects.Apply(model,target,skill,power) then return false end
    state[skill.id] = now+skill.cooldown
    return true
end
function Skills.OnHit(model: Model,target: Model)
    local assigned = assignments(model)
    if not assigned then return end
    for _, assignment in ipairs(assigned) do
        if assignment.trigger == "hit" then
            local skill = Balance.Skill(assignment.skillId)
            if skill then tryCast(model,target,skill) end
        end
    end
end
function Skills.UpdateBuffs(model: Model,attacked: boolean)
    local assigned = assignments(model)
    if not assigned then return end
    for _, assignment in ipairs(assigned) do
        local skill = Balance.Skill(assignment.skillId)
        if not skill or assignment.trigger == "hit" then continue end
        local hp = tonumber(model:GetAttribute("HP")) or 0
        local maxHP = math.max(1, tonumber(model:GetAttribute("MaxHP")) or 1)
        local ready = (assignment.trigger == "attacked" and attacked)
            or (assignment.trigger == "hpBelow" and hp*100/maxHP < assignment.hpBelow)
            or (assignment.trigger == "expired" and not Effects.IsActive(model,skill.effect))
        if ready then tryCast(model,model,skill) end
    end
end
return table.freeze(Skills)

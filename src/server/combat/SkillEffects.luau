--!strict
-- Server effect lifetime owner. One slot per effect and target; no infinite
-- refresh loops, client requests, or direct HP writes.
local Damage = require(script.Parent:WaitForChild("DamageService"))
local Isolation = require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayTestIsolation"))
local Effects = {}
local active = setmetatable({}, {__mode="k"})
local names = {poison="Poison",bleed="Bleed",slow="Slow",root="Root",stun="Stun",silence="Silence",might="Might",haste="Haste"}
local function alive(model: Model): boolean
    return model.Parent ~= nil and model:GetAttribute("LifeState") == "Alive"
end
local function publish(model: Model, state: any)
    local effects = {}
    for effect in pairs(state) do
        table.insert(effects, names[effect])
    end
    table.sort(effects)
    model:SetAttribute("ActiveSkillEffects", if #effects>0 then table.concat(effects," · ") else nil)
    local slow = state.slow
    model:SetAttribute("SkillMoveMultiplier", if state.root or state.stun then 0 elseif slow then 1-slow.power/100 else nil)
    model:SetAttribute("SkillStunned", if state.stun then true else nil)
    model:SetAttribute("SkillSilenced", if state.silence then true else nil)
    model:SetAttribute("SkillDamageMultiplier", if state.might then 1+state.might.power/100 else nil)
    model:SetAttribute("SkillAttackSpeedMultiplier", if state.haste then 1+state.haste.power/100 else nil)
end
function Effects.Clear(target: Model)
    if not active[target] then return end
    active[target] = nil
    if target.Parent then publish(target,{}) end
end
function Effects.Apply(source: Model, target: Model, skill: any, baseDamage: number): boolean
    if not alive(source) or not alive(target) then return false end
    if source ~= target and not Isolation.Allows(source,target) then return false end
    local state = active[target]
    if not state then state = {}; active[target]=state end
    local effect = skill.effect
    if state[effect] then return false end -- same effect never stacks or refreshes
    local entry = {power=skill.power}; state[effect]=entry
    if effect == "stun" then
        target:SetAttribute("SkillStunEpoch", (tonumber(target:GetAttribute("SkillStunEpoch")) or 0)+1)
    end
    publish(target,state)
    if effect == "poison" or effect == "bleed" then
        local count = math.floor(skill.duration/skill.tick+1e-8)
        local tickDamage = baseDamage * skill.power/100
        for i=1,count do
            task.delay(i*skill.tick,function()
                if active[target] ~= state or state[effect] ~= entry or not alive(source) or not alive(target) then return end
                local amount=math.floor(i*tickDamage+0.5)-math.floor((i-1)*tickDamage+0.5)
                if amount>0 then Damage.Apply(source,target,amount,false,true) end
            end)
        end
    end
    task.delay(skill.duration+0.01,function()
        if active[target] ~= state or state[effect] ~= entry then return end
        state[effect]=nil
        if target.Parent then publish(target,state) end
        if next(state)==nil then active[target]=nil end
    end)
    return true
end
function Effects.CanCast(source: Model): boolean
    return alive(source) and source:GetAttribute("SkillStunned") ~= true and source:GetAttribute("SkillSilenced") ~= true
end
function Effects.IsActive(target: Model, effect: string): boolean
    local state = active[target]
    return state ~= nil and state[effect] ~= nil
end
return table.freeze(Effects)

--!strict
-- Server effect lifetime owner. One slot per effect and target; no infinite
-- refresh loops, client requests, or direct HP writes.
local Damage = require(script.Parent:WaitForChild("DamageService"))
local Isolation = require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayTestIsolation"))
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Buffs = require(Shared:WaitForChild("combat"):WaitForChild("BuffDefinitions"))
local Stats = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterStatsService"))
local Effects = {}
local connections = setmetatable({}, {__mode="k"})
local active = setmetatable({}, {__mode="k"})
local names = {poison="Poison",bleed="Bleed",slow="Slow",root="Root",stun="Stun",silence="Silence",might="Might",haste="Haste",earth="Earth",life="Life",wind="Wind"}
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
    local player = Players:GetPlayerFromCharacter(model)
    -- Monsters consume the multiplier in their attack executor. Player damage
    -- is resolved by the existing stat service, never multiplied twice.
    model:SetAttribute("SkillDamageMultiplier", if state.might and not player then 1+state.might.power/100 else nil)
    if player then
        if state.might or state.earth or state.wind then
            Stats.SetModifierSource(model, "skill-buffs", {
                DamagePercent=if state.might then state.might.power else 0,
                MaxHPPercent=if state.earth then state.earth.power else 0,
                RunSpeed=if state.wind then state.wind.power else 0,
            })
        else
            Stats.ClearModifierSource(model,"skill-buffs")
        end
        model:SetAttribute("BuffGain_life", if state.life then state.life.power else nil)
        -- Publish end times after gains so the HUD can report actual stat deltas.
        for _, row in ipairs(Buffs.Rows) do
            local entry = state[row.effect]
            model:SetAttribute("BuffUntil_"..row.effect, if entry then entry.expiresAt else nil)
        end
    end
    model:SetAttribute("SkillAttackSpeedMultiplier", if state.haste then 1+state.haste.power/100 else nil)
end
local function release(target: Model)
    active[target] = nil
    local watchers = connections[target]
    connections[target] = nil
    if watchers then for _, connection in ipairs(watchers) do connection:Disconnect() end end
end
function Effects.Clear(target: Model, preserveBuffs: boolean?)
    local state = active[target]
    if not state then return end
    if preserveBuffs then
        for effect in pairs(state) do
            if not Buffs.ByEffect[effect] then state[effect]=nil end
        end
    else
        table.clear(state)
    end
    if target.Parent then publish(target,state) end
    if next(state)==nil then release(target) end
end
function Effects.Apply(source: Model, target: Model, skill: any, baseDamage: number): boolean
    if not alive(source) or not alive(target) then return false end
    if source ~= target and not Isolation.Allows(source,target) then return false end
    local effect = skill.effect
    if not names[effect] then return false end
    if (effect=="earth" or effect=="life" or effect=="wind") and not Players:GetPlayerFromCharacter(target) then return false end
    local state = active[target]
    if not state then
        state = {}; active[target]=state
        connections[target] = {
            target:GetAttributeChangedSignal("LifeState"):Connect(function()
                if not alive(target) then Effects.Clear(target) end
            end),
            target.Destroying:Connect(function() release(target) end),
        }
    end
    if state[effect] then return false end -- same effect never stacks or refreshes
    local entry = {power=skill.power,expiresAt=Workspace:GetServerTimeNow()+skill.duration}; state[effect]=entry
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
        if next(state)==nil then release(target) end
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

--!strict
-- One exclusive special action, separate from authored normal attack checkpoints.
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance=require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Skills=require(script.Parent:WaitForChild("MonsterSkills"))
local Effects=require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("SkillEffects"))
local Report=require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayCombatReport"))
local Target=require(script.Parent:WaitForChild("MonsterTargetPolicy"))
local Navigation=require(script.Parent:WaitForChild("MonsterChaseNavigation"))
local CombatState=require(script.Parent:WaitForChild("MonsterCombatState"))
local Presentation=require(script.Parent:WaitForChild("MonsterCombatPresentation"))
local CastVisual=require(script.Parent:WaitForChild("MonsterCastPresentation"))
local Facing=require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorFacingTracker"))
local Cast={}
function Cast.Cancel(agent: any)
    local cast=agent.specialCast
    if not cast then return end
    agent.specialCast=nil
    CastVisual.Finish(cast.pose)
    if agent.model.Parent then agent.model:SetAttribute("MonsterCastingSkill",nil) end
end
function Cast.TryBegin(agent: any,target: Model): boolean
    if agent.model:GetAttribute("MonsterSkillCaster")~=true then return false end
    if agent.attacking or os.clock()<agent.nextAttackAt or agent.retreatPending or not Target.IsValid(target) then return false end
    local skill,victim=Skills.Choose(agent.model,target,Target.CanBeginTargetedCast(agent,target))
    if not skill or not victim then return false end
    local buff=victim==agent.model
    local model=agent.model
    local duration=Balance.Rules.monsterCastSeconds
    Skills.Reserve(model,skill)
    Navigation.StopNavigation(agent)
    Presentation.Stop(agent)
    agent.attacking=true; agent.attackSerial+=1
    local serial=agent.attackSerial
    local now=os.clock(); agent.attackEndsAt=now+duration; agent.nextAttackAt=agent.attackEndsAt
    CombatState.SetState(agent,"Attack")
    if not buff then Facing.Track(model,agent.root,agent.humanoid,target,Target.RootOf,true) end
    local cast={pose=CastVisual.Begin(model)}; agent.specialCast=cast
    model:SetAttribute("MonsterCastingSkill",skill.id)
    model:SetAttribute("MonsterAnimationState","atk_special")
    model:SetAttribute("MonsterAttackPhase","Special")
    Report.Cast(model,skill.id)
    task.spawn(function()
        local function valid(): boolean
            return agent.active and agent.attackSerial==serial and agent.specialCast==cast and agent.target==target
                and Target.IsValid(target) and Target.AllowsTarget(agent,target) and Effects.CanCast(model)
        end
        local committed=false
        while valid() do
            local t=math.clamp((os.clock()-now)/duration,0,1)
            CastVisual.Step(cast.pose,t,buff)
            if not committed and t>=.5 then
                committed=true
                -- Targeted cast is committed: no basic-attack arc/range/LOS
                -- reroll at impact. valid() still enforces life, ownership and cancellation.
                if Effects.Apply(model,victim,skill,tonumber(model:GetAttribute("Damage")) or 0) then Report.Cast(model,skill.id,true) end
            end
            if t>=1 then break end
            task.wait(.05)
        end
        if agent.specialCast~=cast then return end
        Cast.Cancel(agent)
        if agent.active and agent.attackSerial==serial then
            agent.attacking=false; agent.attackEndsAt=0
            Facing.Stop(model)
            model:SetAttribute("MonsterAttackPhase","Cooldown")
            Presentation.PlayCombatIdle(agent)
        end
    end)
    return true
end
return table.freeze(Cast)

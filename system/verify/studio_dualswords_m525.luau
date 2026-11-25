-- Studio server command bar; detached character, no live player mutation.
local shared = game:GetService("ReplicatedStorage").Game1Shared
local server = game:GetService("ServerScriptService").Game1Server
local Plan = require(shared.combat.MeleeHitPlan)
local Sessions = require(server.combat.AttackSessionStore)
local Balance = require(shared.balance.Balance)
local model = Instance.new("Model")
local dummy = {} -- only table identity is used as the session key
local ok, err = pcall(function()
    local timing = {duration=1.67,events={HitEnd={time=1},HitFirst={time=0.4}}}
    local single = Plan.Resolve(timing,false,false)
    assert(#single == 1 and single[1].time == 1)
    local dual = Plan.Resolve(timing,true,false)
    assert(#dual == 2 and dual[1].time == 0.4 and dual[2].time == 1)
    for total=1,1000 do
        assert(Plan.Damage(total,1,2)+Plan.Damage(total,2,2)==total)
    end
    timing.events.HitFirst=nil
    assert(not Plan.Resolve(timing,true,false))
    assert(Plan.Resolve(timing,true,true)[1].time==0.5)
    timing.events.HitFirst={time=1}
    assert(not Plan.Resolve(timing,true,true))
    Sessions.Begin(dummy,model,1,2,os.clock()+1)
    assert(not Sessions.MarkMeleeResolved(dummy,model,1,2,2,2))
    assert(Sessions.MarkMeleeResolved(dummy,model,1,2,1,2))
    assert(not Sessions.MarkMeleeResolved(dummy,model,1,2,1,2))
    assert(not Sessions.Get(dummy).hitResolved)
    assert(Sessions.MarkMeleeResolved(dummy,model,1,2,2,2))
    assert(Sessions.Get(dummy).hitResolved)
    assert(not Sessions.MarkMeleeResolved(dummy,model,1,2,2,2))
    Sessions.Begin(dummy,model,2,3,os.clock()+1)
    assert(not Sessions.MarkMeleeResolved(dummy,model,1,2,1,2))
    assert(Sessions.MarkMeleeResolved(dummy,model,2,3))
    for _, id in ipairs({"weapon_033","weapon_034"}) do
        local row=Balance.Weapon(id)
        local _, required=Balance.Grade.ForLevel(row.level)
        assert(required==30 and row.recipe.quantity==2)
    end
end)
Sessions.Forget(dummy)
model:Destroy()
assert(ok,err)
print("[M525] dual hit plan, damage budget, checkpoints and grade passed")

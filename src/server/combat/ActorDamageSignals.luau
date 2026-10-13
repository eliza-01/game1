-- Server-only damage notification. The damage authority never depends on an AI implementation.
local signal = Instance.new("BindableEvent")
local ActorDamageSignals = {}
ActorDamageSignals.Event = signal.Event
function ActorDamageSignals.Publish(attacker: Model?, target: Model, attempted: number, applied: number, killed: boolean)
    -- A fully blocked positive hit still counts as aggression. Zero-power
    -- probes and rejected hits cannot create threat.
    if attempted > 0 then signal:Fire(attacker, target, attempted, applied, killed) end
end
return table.freeze(ActorDamageSignals)

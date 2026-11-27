-- Multipliers are relative to the normal Run speed; never stack route and reengage.
local Speed={}
function Speed.Multiplier(state,config)
    if not state then return 1 end
    if state.blockedPursuit then return config.blockedRetreatSpeedMultiplier end
    if state.mode=="RescueRoute" or (state.mode=="Climb" and state.plan and state.planKind=="RescueRoute") then
        return config.rescueRouteSpeedMultiplier
    end
    if state.reengaging then return config.blockedReengageSpeedMultiplier end
    return 1
end
return table.freeze(Speed)

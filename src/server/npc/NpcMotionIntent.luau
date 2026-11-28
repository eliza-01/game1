-- AI owns locomotion/combat/return intent even before a pose exists.
-- A native presentation consumes the current intent when attached. This is
-- not an attack adapter: attack timing and callbacks require a real pose.
local Intent = {}
local order = {"SetCombatActive", "SetCombatMoving", "SetReturnActive", "SetReturnMoving"}

function Intent.new(binding)
    local values = {}
    local motion = {}
    for _, name in ipairs(order) do
        values[name] = false
        motion[name] = function(value)
            values[name] = value
            if name == "SetReturnActive" and not value then
                values.SetReturnMoving = false
            end
            local presentation = binding:Get()
            if presentation then presentation[name](value) end
        end
    end
    function motion.Replay()
        local presentation = assert(binding:Get(), "MNPC pose is not bound")
        for _, name in ipairs(order) do presentation[name](values[name]) end
    end
    return table.freeze(motion)
end

return table.freeze(Intent)

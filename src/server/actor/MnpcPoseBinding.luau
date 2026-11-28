-- Shared AI-to-pose attachment contract. No Instance or scheduler ownership.
-- A preparation ticket belongs to one incarnation; late completion cannot
-- publish into a closed/released binding. Domain owners dispose rejected payloads.
local Binding = {}

function Binding.new()
    local generation = 0
    local pending = nil
    local payload = nil
    local closed = false
    local binding = {}

    function binding:Begin()
        if closed or pending ~= nil or payload ~= nil then return nil end
        generation += 1
        -- Identity, not only the ordinal, prevents cross-incarnation ABA.
        pending = table.freeze({generation = generation})
        return pending
    end

    function binding:Commit(ticket, value)
        if closed or ticket == nil or ticket ~= pending or value == nil then return false end
        pending = nil
        payload = value
        return true
    end

    function binding:Abort(ticket)
        if ticket == nil or ticket ~= pending then return false end
        pending = nil
        return true
    end

    function binding:Get()
        return payload
    end

    function binding:IsReady()
        return payload ~= nil
    end

    function binding:Release()
        pending = nil
        generation += 1
        local previous = payload
        payload = nil
        return previous
    end

    function binding:Close()
        closed = true
        return binding:Release()
    end

    return table.freeze(binding)
end

return table.freeze(Binding)

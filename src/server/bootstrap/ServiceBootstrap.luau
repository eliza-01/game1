--!strict
-- One owner of startup order, health and failure isolation.
-- The catalog supplies lazy start closures; requiring a broken optional module
-- cannot prevent an unrelated service (including debug remotes) from starting.
local ServiceBootstrap = {}

export type Entry = {
    name: string,
    critical: boolean,
    dependsOn: {string}?,
    start: () -> (),
}

export type Result = {
    status: string,
    critical: boolean,
    error: string?,
}

local lastSnapshot: {[string]: Result} = {}

function ServiceBootstrap.StartAll(entries: {Entry}, report: ((string, Result) -> ())?): ({[string]: Result}, boolean)
    local seen: {[string]: boolean} = {}
    -- Validate the entire catalog before producing any side effects.
    for _, entry in ipairs(entries) do
        assert(type(entry.name) == "string" and entry.name ~= "", "service name is required")
        assert(not seen[entry.name], "duplicate service: " .. entry.name)
        assert(type(entry.start) == "function", "service start callback is required: " .. entry.name)
        seen[entry.name] = true
    end

    local started: {[string]: boolean} = {}
    for _, entry in ipairs(entries) do
        for _, prerequisite in ipairs(entry.dependsOn or {}) do
            assert(seen[prerequisite], "unknown dependency " .. prerequisite .. " for " .. entry.name)
            assert(started[prerequisite], "dependency must precede consumer: " .. prerequisite .. " -> " .. entry.name)
        end
        started[entry.name] = true
    end

    local snapshot: {[string]: Result} = {}
    local coreHealthy = true
    for _, entry in ipairs(entries) do
        local blockedBy: string? = nil
        for _, prerequisite in ipairs(entry.dependsOn or {}) do
            if snapshot[prerequisite].status ~= "ready" then
                blockedBy = prerequisite
                break
            end
        end

        local result: Result
        if blockedBy then
            result = {
                status = "blocked",
                critical = entry.critical,
                error = "dependency not ready: " .. blockedBy,
            }
        else
            local ok, err = pcall(entry.start)
            if ok then
                result = {status = "ready", critical = entry.critical}
            else
                result = {status = "failed", critical = entry.critical, error = tostring(err)}
            end
        end
        snapshot[entry.name] = result
        if entry.critical and result.status ~= "ready" then
            coreHealthy = false
        end
        if report then
            report(entry.name, result)
        end
    end
    lastSnapshot = snapshot
    return snapshot, coreHealthy
end

function ServiceBootstrap.GetSnapshot(): {[string]: Result}
    local copy: {[string]: Result} = {}
    for name, value in pairs(lastSnapshot) do
        copy[name] = table.clone(value)
    end
    return copy
end

return ServiceBootstrap

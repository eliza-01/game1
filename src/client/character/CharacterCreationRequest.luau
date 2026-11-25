--!strict
-- RemoteFunction yields have no built-in deadline. Keep one actual invocation
-- per remote, even after a local timeout. Never send a duplicate while the
-- previous request is still executing on the server.
local Request = {}
local active: {[RemoteFunction]: any} = {}
function Request.Invoke(remote: RemoteFunction, current: () -> boolean, timeout: number, ...: any): (boolean, any)
    local deadline = os.clock() + timeout
    while active[remote] and current() and os.clock() < deadline do task.wait(0.05) end
    if not current() then return false, "cancelled" end
    if os.clock() >= deadline then return false, "request_timeout" end
    local args = table.pack(...)
    local result: any = {finished = false, ok = false}
    active[remote] = result
    task.spawn(function()
        result.ok, result.value = pcall(remote.InvokeServer, remote, table.unpack(args, 1, args.n))
        result.finished = true
        if active[remote] == result then active[remote] = nil end
    end)
    while current() and not result.finished and os.clock() < deadline do task.wait(0.05) end
    if not current() then return false, "cancelled" end
    if not result.finished then return false, "request_timeout" end
    return result.ok, result.value
end
return table.freeze(Request)

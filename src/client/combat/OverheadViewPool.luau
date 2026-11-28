-- A bounded cache of unbound views, not a cap on visible combat UI.
local Pool = {}
Pool.__index = Pool
function Pool.new(factory, idleLimit, ttl)
    return setmetatable({factory = factory, idleLimit = idleLimit, ttl = ttl,
        idle = {}, active = {}}, Pool)
end
function Pool:Acquire(owner, parent, anchor, style, now)
    assert(not self.active[owner], "duplicate overhead lease")
    self:Expire(now)
    local entry = table.remove(self.idle)
    local view
    local ok, err = pcall(function()
        view = entry and entry.view or self.factory()
        view.Bind(parent, owner, anchor, style)
    end)
    if not ok then
        if view then view.Destroy() end
        warn("[Overhead] Bind failed: " .. tostring(err))
        return nil
    end
    self.active[owner] = view
    return view
end
function Pool:Release(owner, now, discard)
    local view = self.active[owner]
    if not view then return end
    self.active[owner] = nil
    if discard or #self.idle >= self.idleLimit then view.Destroy(); return end
    local ok, err = pcall(view.Unbind)
    if not ok then
        warn("[Overhead] Unbind failed: " .. tostring(err))
        view.Destroy()
        return
    end
    table.insert(self.idle, {view = view, expires = now + self.ttl})
end
function Pool:Expire(now)
    for i = #self.idle, 1, -1 do
        if self.idle[i].expires <= now then
            local entry = table.remove(self.idle, i)
            entry.view.Destroy()
        end
    end
end
function Pool:Clear()
    for owner in pairs(self.active) do self:Release(owner, 0, true) end
    for _, entry in ipairs(self.idle) do entry.view.Destroy() end
    table.clear(self.idle)
end
return table.freeze(Pool)

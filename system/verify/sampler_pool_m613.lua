local Pool = dofile('src/client/actor/SamplerPool.luau')
local now, created, destroyed = 0, 0, 0
local function factory()
    created = created + 1
    return { running = true,
        Resume = function(self, speed, phase) self.running = true; self.speed = speed; self.phase = phase end,
        Suspend = function(self) self.running = false end,
        Destroy = function(self) assert(not self.dead); self.dead = true; destroyed = destroyed + 1 end }
end
local p = Pool.new(2, 8, function() return now end)
local a = assert(p:Acquire('npc|a', factory, 1, 0))
local b = assert(p:Acquire('monster|a', factory, 1, 0))
assert(a ~= b and p.resident == 2)
local none, reason = p:Acquire('npc|a', factory, 1, 0)
assert(not none and reason == 'budget' and created == 2)
p:Release(a); p:Release(a)
assert(not a.running and p.resident == 2)
local same = assert(p:Acquire('npc|a', factory, 2, 0.4))
assert(same == a and a.running and a.speed == 2 and a.phase == 0.4)
p:Release(a)
now = 1
p:Release(b)
local c = assert(p:Acquire('monster|b', factory, 1, 0))
assert(a.dead and not b.dead and c ~= a and p.resident == 2)
now = 10; p:Cleanup(now)
assert(b.dead and not c.dead and p.resident == 1)
assert(not p:Acquire('failed', function() error('load failed') end, 1, 0))
assert(p.resident == 1)
local co = coroutine.create(function()
    return p:Acquire('pending', function() coroutine.yield(); return factory() end, 1, 0)
end)
assert(coroutine.resume(co)); assert(p.resident == 2)
assert(not p:Acquire('overflow', factory, 1, 0))
local ok, d = coroutine.resume(co); assert(ok and d and p.resident == 2)
p:Release(c); p:Release(d)
now = 20; p:Cleanup(now)
assert(p.resident == 0 and destroyed == created)
-- Reuse failure must release the reservation and destroy the broken sampler.
local e = assert(p:Acquire('x', factory, 1, 0)); p:Release(e)
e.Resume = function() error('resume failed') end
assert(not p:Acquire('x', factory, 1, 0) and e.dead and p.resident == 0)
print('M613 shared sampler pool: OK')

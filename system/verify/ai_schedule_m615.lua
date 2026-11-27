local Queue = dofile('src/server/actor/ActorAIScheduleQueue.luau')
local now, pending, errors = 0, {}, {}
local q = Queue.new(function() return now end, function(fn, ...)
    local thread = coroutine.create(fn)
    local ok, err = coroutine.resume(thread, ...)
    assert(ok, err)
    if coroutine.status(thread) ~= 'dead' then pending[#pending+1] = thread end
end, function(err) errors[#errors+1] = err end)
local function pump(t) now=t; q:Pump(t) end
local calls, stopped = {}, 0
local function step(key, time) calls[#calls+1] = {key,time} end
assert(q:Register('m', .1, .15, step))
assert(not q:Register('m', .1, .15, step))
assert(q:Register('npc', .1, .1, step))
pump(.09); assert(#calls==0)
pump(.1); assert(#calls==1 and calls[1][1]=='npc')
pump(.15); assert(#calls==2 and calls[2][1]=='m')
pump(.2); assert(#calls==3 and calls[3][1]=='npc')
pump(1); assert(#calls==5) -- no catch-up burst
q:Remove('npc'); q:Remove('m'); assert(#q.heap==0 and next(q.entries)==nil)
local count=0
q:Register('yield', .1, .1, function() count=count+1; coroutine.yield(); count=count+1 end)
q:Register('healthy', .1, .1, step)
pump(1.11); assert(count==1 and #pending==1 and calls[#calls][1]=='healthy')
pump(1.5); assert(count==1 and calls[#calls][1]=='healthy')
q:Remove('yield'); assert(coroutine.resume(table.remove(pending))); assert(count==2)
assert(q.entries.yield==nil)
q:Remove('healthy')
q:Register('yield', .1, .1, function() coroutine.yield() end)
pump(1.61); assert(#pending==1)
now=2; assert(coroutine.resume(table.remove(pending))); assert(q.heap[1].due==2.1)
pump(2.09); assert(#pending==0); pump(2.1); assert(#pending==1)
q:Remove('yield'); assert(coroutine.resume(table.remove(pending)))
q:Register('bad', .1, .1, function() error('boom') end, function() stopped=stopped+1 end)
q:Register('retry', .1, .1, function() error('retry') end)
q:Register('terminal', .1, .1, function() return false end, function() stopped=stopped+1 end)
pump(2.21); assert(stopped==2 and #errors==2 and q.entries.bad==nil and q.entries.terminal==nil and q.entries.retry)
q:Remove('retry')
-- Heap removal, FIFO tie order and mass registration/cleanup.
local order={}
for i=1,1000 do q:Register(i, .1, .1+(i%7)*.01, function(k) order[#order+1]=k; return false end) end
for i=3,1000,3 do q:Remove(i) end
pump(3); assert(#order==667 and #q.heap==0 and next(q.entries)==nil)
for i=2,#order do local a,b=order[i-1],order[i]; assert(a%7<b%7 or (a%7==b%7 and a<b)) end
-- Phase-locked NPC keeps nominal cadence when Heartbeat runs late.
q:Register('phase', .1, .1, step, nil, true)
pump(3.13); assert(math.abs(q.heap[1].due-3.2)<1e-8)
pump(3.46); assert(math.abs(q.heap[1].due-3.5)<1e-8)
q:Remove('phase'); assert(#q.heap==0)
-- Removal before dispatch must not execute a stale callback or reinsert it.
local deferred
local d=Queue.new(function() return now end, function(fn, ...) deferred={fn,...} end, function(err) error(err) end)
d:Register('same', .1, .1, function() error('stale callback') end)
now=4; d:Pump(now); d:Remove('same'); d:Register('same', .1, .1, step)
deferred[1](deferred[2], deferred[3]); assert(#d.heap==1 and d.entries.same)
print('AI deadline queue: lifecycle, cadence, FIFO, yielding, failure isolation, 1000 agents OK')

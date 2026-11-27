local Queue = dofile('src/server/actor/NavigationRequestQueue.luau')
local now, errors, disposed = 0,0,0
local threads, started = {},{}
local function spawn(fn)
    local thread = coroutine.create(fn)
    threads[#threads+1] = thread
    assert(coroutine.resume(thread))
end
local q = Queue.new(function() return now end,spawn,function() errors=errors+1 end,2,8)
local function req(id)
    return q:Request(id,function(ticket)
        started[#started+1]={id,now,ticket.destination}
        coroutine.yield()
        if id=='error' then error('mock') end
        return id
    end,function() disposed=disposed+1 end)
end
local a,b,c,d=req('a'),req('b'),req('c'),req('d')
assert(not req('a'))
q:Cancel(c)
q:Pump(); assert(q.active==1 and a.status=='Running')
now=.10; q:Pump(); assert(q.active==1)
now=.125; q:Pump(); assert(q.active==2)
now=1; q:Pump(); assert(d.status=='Queued')
q:Cancel(a); assert(not req('a') and q.active==2)
assert(coroutine.resume(threads[1])); assert(disposed==1 and q.active==1)
d.destination='latest'; q:Pump(); assert(started[3][1]=='d' and started[3][3]=='latest')
assert(coroutine.resume(threads[2])); local ready,value=q:Take(b); assert(ready and value=='b' and not q:Take(b))
assert(coroutine.resume(threads[3])); q:Cancel(d); assert(disposed==2)
local err=req('error'); now=2; q:Pump(); assert(coroutine.resume(threads[4])); assert(errors==1 and q.active==0 and q:Take(err))
assert(not next(q.owners) and not q.head and not q.tail)
-- Contention, FIFO ordering, no catch-up burst, constant owner cleanup.
local tickets={}
for i=1,1000 do tickets[i]=req(i) end
for i=1,1000 do
    now=now+.25; q:Pump(); q:Pump()
    assert(q.active==1 and started[#started][1]==i)
    assert(coroutine.resume(threads[#threads])); assert(q:Take(tickets[i]))
end
assert(not next(q.owners) and not q.head and not q.tail and q.active==0)
print('Navigation queue: 1000 FIFO requests; rate/concurrency, cancel, error, update and cleanup OK')

-- FIFO admission for yielding requests. An owner has at most one outstanding
-- ticket; cancellation of running work retains its slot until it really exits.
local Queue = {}
Queue.__index = Queue

function Queue.new(clock, spawn, report, concurrent, perSecond)
    assert(concurrent >= 1 and perSecond > 0)
    return setmetatable({clock=clock, spawn=spawn, report=report, concurrent=concurrent,
        spacing=1/perSecond, nextStart=0, active=0, owners={}, head=nil, tail=nil}, Queue)
end

function Queue:_unlink(ticket)
    if ticket.prev then ticket.prev.next = ticket.next else self.head = ticket.next end
    if ticket.next then ticket.next.prev = ticket.prev else self.tail = ticket.prev end
    ticket.prev, ticket.next = nil, nil
end

function Queue:Request(owner, work, dispose)
    if self.owners[owner] then return nil end
    local ticket = {owner=owner, work=work, dispose=dispose, status="Queued", prev=self.tail}
    if self.tail then self.tail.next = ticket else self.head = ticket end
    self.tail = ticket
    self.owners[owner] = ticket
    return ticket
end

function Queue:Cancel(ticket)
    if not ticket or self.owners[ticket.owner] ~= ticket then return end
    if ticket.status == "Running" or ticket.status == "Cancelled" then
        ticket.status = "Cancelled"
        return
    end
    if ticket.status == "Queued" then self:_unlink(ticket) end
    self.owners[ticket.owner] = nil
    ticket.status = "Cancelled"
    if ticket.result then ticket.dispose(ticket.result); ticket.result = nil end
end

function Queue:Take(ticket)
    if not ticket or ticket.status ~= "Ready" or self.owners[ticket.owner] ~= ticket then return false end
    self.owners[ticket.owner] = nil
    local result = ticket.result
    ticket.result = nil
    ticket.status = "Taken"
    return true, result
end

function Queue:Pump()
    if not self.head or self.active >= self.concurrent then return end
    local now = self.clock()
    if now < self.nextStart then return end
    local ticket = self.head
    self:_unlink(ticket)
    ticket.status = "Running"
    self.active = self.active + 1
    self.nextStart = now + self.spacing -- no catch-up bursts after a slow frame
    self.spawn(function()
        local ok, result = xpcall(ticket.work, debug.traceback, ticket)
        self.active = self.active - 1
        if not ok then self.report(result); result = nil end
        if ticket.status == "Cancelled" then
            self.owners[ticket.owner] = nil
            if result then ticket.dispose(result) end
        else
            ticket.result = result
            ticket.status = "Ready"
        end
    end)
end

return Queue

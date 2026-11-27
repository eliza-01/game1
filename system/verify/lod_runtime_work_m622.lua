-- Engine-independent scheduler and lifecycle oracle. Roblox geometry, actual
-- clone/parent behavior and weld physics still need Studio acceptance.
local Job = dofile('src/client/world/LodAssemblyJob.luau')
local Work = dofile('src/client/world/LodRuntimeWork.luau')
local live = 0
local function node(kind, parent)
    live = live + 1
    local object = {kind=kind, Parent=parent, children={}, destroyed=false}
    function object:IsA(class) return self.kind == class end
    function object:GetChildren() return self.children end
    function object:Destroy()
        if self.destroyed then return end
        self.destroyed = true
        self.Parent = nil
        live = live - 1
        for _, child in ipairs(self.children) do child:Destroy() end
    end
    if type(parent) == 'table' then parent.children[#parent.children+1] = object end
    return object
end
local function fixture()
    local work = Work.new()
    local scene = 'scene'
    local callbacks = {}
    function callbacks.valid(entry, job)
        return entry.valid and (not job or job.epoch == entry.epoch)
    end
    function callbacks.prepare(entry)
        local job = Job.new(function(j)
            local bundle = j:Own(node('Model'))
            j.bundle = bundle
            j:Unit()
            for i = 1, entry.count do
                local part = j:Own(node('MeshPart'))
                j:Unit() -- cancellation also owns an unparented clone
                if entry.failAt == i then error('synthetic assembly error') end
                part.configured = true
                j:Unit()
                part.Parent = bundle
                bundle.children[#bundle.children+1] = part
                j:Unit()
                if entry.composite then
                    local weld = j:Own(node('Weld', part))
                    j.links[#j.links+1] = weld
                    j:Unit()
                end
            end
        end)
        job.epoch = entry.epoch
        if entry.composite then job.links = {} end
        return job
    end
    function callbacks.failed(entry, reason, retryable)
        entry.failed = reason
        entry.retryable = retryable
        entry.valid = false
    end
    function callbacks.commit(entry, job, owner)
        if job and entry.proxyChanged then return false, 'component unavailable at commit', true end
        if job then
            assert(job.state == 'ready')
            assert(job.bundle.Parent == nil)
            assert(#job.bundle.children == entry.count)
            job.bundle.Parent = scene
        end
        if entry.old then owner:Retire(entry.old) end
        entry.old = job and job:Release() or nil
        entry.valid = false
        entry.committed = true
        return true
    end
    local function step()
        local stats = work:Step(callbacks)
        assert(stats.build <= Work.BuildBudget)
        assert(stats.cleanup <= Work.CleanupBudget)
        assert(stats.commit <= Work.CommitBudget)
        assert(#work.retired <= 2)
        return stats
    end
    local function drain()
        for _ = 1, 200 do
            step()
            if not work.active and #work.retired == 0 then return end
        end
        error('work did not drain')
    end
    return work, step, drain
end
for _, count in ipairs({1, 8, 32, 64}) do
    for _, composite in ipairs({false, true}) do
        local work, step, drain = fixture()
        local old = node('MeshPart', 'scene')
        local entry = {variant='LOD1', valid=true, epoch=1, count=count, old=old, composite=composite}
        work:Begin({entry})
        local frames = 0
        repeat
            step(); frames = frames + 1
            if not entry.committed then assert(old.Parent == 'scene') end
            assert(frames < 200)
        until entry.committed
        if count >= 8 then assert(frames > 1) end
        assert(old.Parent == nil and entry.old.Parent == 'scene')
        drain()
        assert(old.destroyed)
        entry.old:Destroy()
        work:Destroy()
        assert(live == 0)
    end
end
-- Epoch/desired cancellation and unparented clone cleanup.
for _, reason in ipairs({'desired','generation','failure','proxy'}) do
    local work, step, drain = fixture()
    local old = node('MeshPart', 'scene')
    local entry = {variant='FULL', valid=true, epoch=1, count=64, old=old, composite=true}
    if reason == 'failure' then entry.failAt = 3 end
    if reason == 'proxy' then entry.proxyChanged = true end
    work:Begin({entry}); step()
    if reason == 'desired' then entry.valid = false end
    if reason == 'generation' then entry.epoch = 2 end
    drain()
    assert(not entry.committed and old.Parent == 'scene')
    if reason == 'failure' or reason == 'proxy' then assert(entry.failed) end
    if reason == 'proxy' then assert(entry.retryable) end
    assert(live == 1)
    old:Destroy(); work:Destroy(); assert(live == 0)
end
-- Unload old geometry while a large composite builds. 64-link commit must
-- eventually reserve an entire atomic commit slot, even under unload pressure.
local work, step, drain = fixture()
local build = {variant='FULL', valid=true, count=64, epoch=1, composite=true}
local entries = {build}
for i=1,80 do entries[#entries+1] = {variant='UNLOADED', valid=true, old=node('MeshPart','scene')} end
work:Begin(entries)
for i=1,160 do step() end
assert(build.committed)
for i=2,#entries do assert(entries[i].committed) end
drain(); build.old:Destroy(); work:Destroy(); assert(live == 0)
print('M622 oracle: 1/8/32/64 static and composite; budget, atomic swap, cancellation, proxy change, failure, concurrent unload and cleanup passed')

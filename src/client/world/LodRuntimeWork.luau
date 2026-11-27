-- One active detached build, bounded retired bundles, no independent scheduler.
-- Counters are operation groups, not a CPU-time deadline. Parent/Destroy/Clone
-- and the atomic composite bind can have engine-dependent costs.
local Work = {}
Work.__index = Work
Work.BuildBudget = 12
Work.CleanupBudget = 8
Work.LookupBudget = 16 -- bounded candidate checks per category per frame
Work.CommitBudget = 132 -- max 64 proxy checks + 64 bindings + root/swap operations

function Work.new()
    return setmetatable({retired={}, active=nil, unloads={}, builds={}, unloadIndex=1, buildIndex=1, last={build=0, cleanup=0, commit=0}}, Work)
end

-- Rebuild iteration cursors only at the distance observation, not per frame.
function Work:Begin(entries)
    self.unloads, self.builds = {}, {}
    self.unloadIndex, self.buildIndex = 1, 1
    for _, entry in ipairs(entries) do
        local list = entry.variant == "UNLOADED" and self.unloads or self.builds
        list[#list+1] = entry
    end
end

function Work:_next(list, cursor, valid)
    local checked = 0
    while self[cursor] <= #list and checked < self.LookupBudget do
        checked = checked + 1
        local entry = list[self[cursor]]
        self[cursor] = self[cursor] + 1
        if valid(entry) then return entry end
    end
    return nil
end

function Work:Retire(bundle)
    if not bundle then return end
    if bundle.Parent then bundle.Parent = nil end
    local owned = {bundle}
    if not bundle:IsA("MeshPart") then
        for _, child in ipairs(bundle:GetChildren()) do owned[#owned+1] = child end
    end
    self.retired[#self.retired+1] = owned
end

function Work:Cancel(stale)
    if not self.active then return end
    local job = self.active.job
    if self.diagnostics and self.diagnostics.enabled then
        self.diagnostics:Add("cancelledJobs")
        if stale then self.diagnostics:Add("staleJobCancels") end
    end
    if job.bundle and job.bundle.Parent then job.bundle.Parent = nil end
    local owned = job:Cancel()
    if #owned > 0 then self.retired[#self.retired+1] = owned end
    self.active = nil
end

function Work:Cleanup(limit)
    local used = 0
    while used < limit and #self.retired > 0 do
        local owned = self.retired[1]
        local instance = table.remove(owned)
        if instance then instance:Destroy(); used = used + 1 end
        if #owned == 0 then table.remove(self.retired, 1) end
    end
    return used
end

function Work:_committed(entry, job)
    local d = self.diagnostics
    if not d or not d.enabled then return end
    d:Add("commits")
    d:Add(job and "buildCommits" or "unloadCommits")
    if job then d:Add("weldBindings", #(job.links or {})) end
    if entry.createdAt and entry.createdAt >= d.startedAt then d:Latency(d.clock()-entry.createdAt) end
    local record = entry.record
    if record and record.actual == record.desired and record.diagnosticDesiredAt then
        if record.diagnosticDesiredAt >= d.startedAt then d:DesiredLatency(d.clock()-record.diagnosticDesiredAt) end
        record.diagnosticDesiredAt = nil
    end
end

function Work:_failed(entry, reason, retryable, callbacks)
    local d = self.diagnostics
    if d and d.enabled then d:Add(retryable and "retryableAttempts" or "failedAttempts") end
    callbacks.failed(entry, reason, retryable)
end

function Work:Step(callbacks)
    local stats = {build=0, cleanup=self:Cleanup(self.CleanupBudget), commit=0}
    self.last = stats
    if self.active and not callbacks.valid(self.active.entry, self.active.job) then self:Cancel(true) end
    -- Unloads progress independently of a large build. Reserve a retirement
    -- slot for cancellation or replacement; never grow an unbounded backlog.
    local ready = self.active and self.active.job.state == "ready"
    local reserveCommit = ready and 4 + 2 * #(self.active.job.links or {}) + 2 > self.CommitBudget
    if #self.retired == 0 and not reserveCommit then
        local entry = self:_next(self.unloads, "unloadIndex", callbacks.valid)
        if entry then
            local ok, reason, retryable = callbacks.commit(entry, nil, self)
            if ok then self:_committed(entry, nil) else self:_failed(entry, reason, retryable, callbacks) end
            stats.commit = 2
        end
    end
    if not self.active and #self.retired <= 1 then
        local entry = self:_next(self.builds, "buildIndex", callbacks.valid)
        if entry then
            local ok, job, reason, retryable = pcall(callbacks.prepare, entry)
            if not ok then self:_failed(entry, job, false, callbacks)
            elseif job then
                job.diagnostics = self.diagnostics
                self.active = {entry=entry, job=job}
            else self:_failed(entry, reason, retryable == true, callbacks) end
            -- One start attempt per frame, even if a proxy is absent.
            stats.build = 1
        end
    end
    local active = self.active
    if not active then return stats end
    local job, entry = active.job, active.entry
    stats.build = stats.build + job:Advance(self.BuildBudget - stats.build)
    if self.diagnostics and self.diagnostics.enabled then self.diagnostics:Peak("stagingInstances", #job.owned) end
    if job.state == "failed" then
        self:_failed(entry, job.problem, job.retryable == true, callbacks)
        self:Cancel()
    elseif job.state == "ready" and #self.retired <= 1 then
        local cost = 4 + 2 * #(job.links or {})
        if stats.commit + cost <= self.CommitBudget then
            if not callbacks.valid(entry, job) then self:Cancel(true)
            else
                stats.commit = stats.commit + cost
                local ok, reason, retryable = callbacks.commit(entry, job, self)
                if ok then self:_committed(entry, job); self.active = nil
                else self:_failed(entry, reason, retryable == true, callbacks); self:Cancel() end
            end
        end
    end
    return stats
end

function Work:Destroy()
    self:Cancel()
    while #self.retired > 0 do self:Cleanup(self.CleanupBudget) end
end

return Work

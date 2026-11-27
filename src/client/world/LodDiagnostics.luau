-- Opt-in, bounded local capture. No polling loop, remotes or persistent data.
-- Work units are scheduler groups, not milliseconds or engine API call counts.
local Capture = {}
Capture.__index = Capture
local LIMIT = 12000

function Capture.new(clock)
    return setmetatable({clock=clock or os.clock, enabled=false}, Capture)
end

function Capture:Start(cacheStats)
    self.enabled = true
    self.startedAt = self.clock()
    self.counts = {}
    for _, key in ipairs({"observations", "spatialQueries", "candidateVisits", "distanceResolves", "workDistanceChecks",
        "localSorts", "compositePathEvents", "compositeRootChanges", "compositeDiscoveryVisits",
        "compositeEffectEvents", "compositeEffectVisits", "compositeEffectWrites", "buildUnits", "cleanupUnits", "commitUnits", "commits", "buildCommits",
        "unloadCommits", "cancelledJobs", "staleJobCancels", "retryableAttempts", "failedAttempts", "meshClones", "weldCreates", "weldBindings",
        "taggedVisualVisits", "asyncStarts", "asyncFailures", "asyncDiscards"}) do
        self.counts[key] = 0
    end
    self.peaks = {queueSize=0, queueAgeMs=0, localCandidates=0, pendingAsync=0, stagingInstances=0, retiredBundles=0, buildUnits=0, cleanupUnits=0, commitUnits=0}
    self.samples = {}
    self.cacheStart = cacheStats or {}
    self.frames = 0
    self.frameSum = 0
    self.frameMax = 0
    self.callbackSamples = {}
    self.callbackSum = 0
    self.callbackMax = 0
    self.desiredSamples = {}
    self.desiredCount = 0
    self.desiredSum = 0
    self.desiredMax = 0
    self.latencies = {}
    self.latencyCount = 0
    self.latencySum = 0
    self.latencyMax = 0
end

function Capture:Add(key, amount)
    if not self.enabled then return end
    self.counts[key] = (self.counts[key] or 0) + (amount or 1)
end

function Capture:Peak(key, value)
    if not self.enabled then return end
    self.peaks[key] = math.max(self.peaks[key] or 0, value)
end

function Capture:Frame(dt, stats, elapsed)
    if not self.enabled then return end
    self.frames = self.frames + 1
    local ms = dt * 1000
    self.frameSum = self.frameSum + ms
    self.frameMax = math.max(self.frameMax, ms)
    if #self.samples < LIMIT then self.samples[#self.samples+1] = ms end
    local callbackMs = (elapsed or 0) * 1000
    self.callbackSum = self.callbackSum + callbackMs
    self.callbackMax = math.max(self.callbackMax, callbackMs)
    if #self.callbackSamples < LIMIT then self.callbackSamples[#self.callbackSamples+1] = callbackMs end
    for _, key in ipairs({"build", "cleanup", "commit"}) do
        local value = stats[key] or 0
        self:Add(key .. "Units", value)
        self:Peak(key .. "Units", value)
    end
end

function Capture:Latency(seconds)
    if not self.enabled then return end
    local ms = math.max(0, seconds * 1000)
    self.latencyCount = self.latencyCount + 1
    self.latencySum = self.latencySum + ms
    self.latencyMax = math.max(self.latencyMax, ms)
    if #self.latencies < LIMIT then self.latencies[#self.latencies+1] = ms end
end

function Capture:DesiredLatency(seconds)
    if not self.enabled then return end
    local ms = math.max(0, seconds*1000)
    self.desiredCount = self.desiredCount + 1
    self.desiredSum = self.desiredSum + ms
    self.desiredMax = math.max(self.desiredMax, ms)
    if #self.desiredSamples < LIMIT then self.desiredSamples[#self.desiredSamples+1] = ms end
end

local function distribution(samples, count, sum, maximum)
    table.sort(samples)
    local function percentile(p)
        return samples[math.ceil(#samples*p)] or 0
    end
    return {count=count, sampled=#samples, mean=count > 0 and sum/count or 0,
        max=maximum, p50=percentile(.50), p95=percentile(.95), p99=percentile(.99)}
end

function Capture:Finish(cacheStats, gauges)
    if not self.enabled then return nil end
    self.enabled = false
    for _, key in ipairs({"prototypeRefreshes", "contractChecks", "retryScans"}) do
        self.counts[key] = (cacheStats[key] or 0) - (self.cacheStart[key] or 0)
    end
    return {seconds=self.clock()-self.startedAt, counters=self.counts, peaks=self.peaks,
        gauges=gauges, heartbeatMs=distribution(self.samples,self.frames,self.frameSum,self.frameMax),
        queueResidenceMs=distribution(self.latencies,self.latencyCount,self.latencySum,self.latencyMax),
        callbackElapsedMs=distribution(self.callbackSamples,self.frames,self.callbackSum,self.callbackMax),
        desiredToActualMs=distribution(self.desiredSamples,self.desiredCount,self.desiredSum,self.desiredMax)}
end

return Capture

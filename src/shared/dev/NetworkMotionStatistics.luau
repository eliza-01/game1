-- Read-only, bounded statistics. Pure numeric core, independent of Roblox instances.
local Statistics = {}
local LIMIT = 2048
local BIN_SECONDS = 0.5
local DURATION = 8

local function channel()
    return {samples = {}, integral = 0, seconds = 0}
end
local function add(c, value, dt)
    c.samples[#c.samples + 1] = value
    c.integral = c.integral + value * dt
    c.seconds = c.seconds + dt
end
local function summary(c)
    local n = #c.samples
    if n == 0 then return {mean = 0, p05 = 0, p95 = 0, max = 0} end
    table.sort(c.samples)
    return {mean = c.integral / c.seconds, p05 = c.samples[math.max(1, math.ceil(n * .05))],
        p95 = c.samples[math.ceil(n * .95)], max = c.samples[n]}
end
function Statistics.New()
    return {physical = channel(), render = channel(), velocity = channel(), frame = channel(),
        count = 0, seconds = 0, movingStops = 0, bins = {}, hasRender = false}
end
function Statistics.Add(state, dt, physicalDistance, renderDistance, velocity)
    if dt <= 0 or state.count >= LIMIT then return false end
    state.count = state.count + 1
    state.seconds = state.seconds + dt
    local physical = physicalDistance / dt
    add(state.physical, physical, dt)
    add(state.velocity, velocity, dt)
    add(state.frame, dt * 1000, dt)
    if renderDistance ~= nil then
        state.hasRender = true
        local render = renderDistance / dt
        add(state.render, render, dt)
        if velocity >= 2 and render < .1 then state.movingStops = state.movingStops + 1 end
    end
    -- Half-second bins use measured elapsed time, not a guessed frame rate.
    local index = math.min(math.ceil(DURATION / BIN_SECONDS), math.floor((state.seconds - dt * .5) / BIN_SECONDS) + 1)
    local bin = state.bins[index]
    if not bin then bin = {seconds = 0, physical = 0, render = 0, velocity = 0}; state.bins[index] = bin end
    bin.seconds = bin.seconds + dt
    bin.physical = bin.physical + physicalDistance
    bin.render = bin.render + (renderDistance or 0)
    bin.velocity = bin.velocity + velocity * dt
    return state.count < LIMIT
end
function Statistics.Finish(state)
    local bins = {}
    for i = 1, math.ceil(DURATION / BIN_SECONDS) do
        local b = state.bins[i]
        if b then bins[i] = {physical = b.physical / b.seconds, render = b.render / b.seconds,
            velocity = b.velocity / b.seconds, seconds = b.seconds} end
    end
    return {frames = state.count, seconds = state.seconds, fps = state.count / math.max(state.seconds, .001),
        physical = summary(state.physical), render = state.hasRender and summary(state.render) or nil,
        velocity = summary(state.velocity), frame = summary(state.frame), movingStops = state.movingStops, bins = bins,
        capped = state.count >= LIMIT}
end
-- Owner reports are diagnostic only and originate on an untrusted client.
-- Copy bounded, finite numeric fields; never forward an arbitrary client table.
local function finite(value, low, high)
    return type(value) == "number" and value >= low and value <= high
end
function Statistics.ValidateOwner(report, startAt)
    if type(report) ~= "table" or report.reason ~= "complete"
        or not finite(report.seconds, 7, 10) or not finite(report.frames, 1, LIMIT)
        or report.frames % 1 ~= 0
        or not finite(report.actualStart, startAt, startAt + 0.5)
        or not finite(report.actualEnd, startAt + DURATION, startAt + DURATION + 1) then return nil end
    local result = {seconds = report.seconds, frames = report.frames,
        fps = report.frames / report.seconds, reason = "complete",
        actualStart = report.actualStart, actualEnd = report.actualEnd}
    for _, name in ipairs({"physical", "render", "velocity", "frame"}) do
        local source = report[name]
        if type(source) ~= "table" then return nil end
        local target = {}
        for _, key in ipairs({"mean", "p05", "p95", "max"}) do
            if not finite(source[key], 0, 10000) then return nil end
            target[key] = source[key]
        end
        if target.p05 > target.p95 or target.p95 > target.max then return nil end
        result[name] = target
    end
    return result
end
Statistics.Duration = DURATION
Statistics.Limit = LIMIT
return Statistics

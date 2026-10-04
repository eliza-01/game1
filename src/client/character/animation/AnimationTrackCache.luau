local ContentProvider = game:GetService("ContentProvider")
local RunService = game:GetService("RunService")

local AnimationTrackCache = {}
AnimationTrackCache.__index = AnimationTrackCache

local PRIORITIES = {
	Idle = Enum.AnimationPriority.Idle,
	Movement = Enum.AnimationPriority.Movement,
	Action = Enum.AnimationPriority.Action,
	Action2 = Enum.AnimationPriority.Action2,
	Action3 = Enum.AnimationPriority.Action3,
	Action4 = Enum.AnimationPriority.Action4,
}

local function priorityFromName(name: string): Enum.AnimationPriority
	return PRIORITIES[name] or Enum.AnimationPriority.Movement
end

local function applyDescriptor(track: AnimationTrack, descriptor)
	track.Looped = descriptor.looped == true
	track.Priority = priorityFromName(tostring(descriptor.priority or "Movement"))
end

function AnimationTrackCache.new(animator: Animator)
	return setmetatable({
		animator = animator,
		entries = {},
		destroyed = false,
	}, AnimationTrackCache)
end

function AnimationTrackCache:Get(descriptor)
	if self.destroyed or not descriptor then
		return nil
	end
	local clipId = tostring(descriptor.clipId or descriptor.animationId or "")
	local animationId = tostring(descriptor.animationId or "")
	if clipId == "" or animationId == "" then
		return nil
	end
	local cached = self.entries[clipId]
	if cached then
		applyDescriptor(cached.track, descriptor)
		return cached.track
	end
	local animation = Instance.new("Animation")
	animation.Name = clipId
	animation.AnimationId = animationId
	local ok, trackOrError = pcall(function()
		return self.animator:LoadAnimation(animation)
	end)
	if not ok then
		animation:Destroy()
		warn(("[game1][animation] failed to load %s: %s"):format(clipId, tostring(trackOrError)))
		return nil
	end
	local track = trackOrError :: AnimationTrack
	applyDescriptor(track, descriptor)
	self.entries[clipId] = { animation = animation, track = track }
	return track
end

function AnimationTrackCache:IsLoaded(track: AnimationTrack?): boolean
	return track ~= nil and (tonumber(track.Length) or 0) > 0.01
end

function AnimationTrackCache:WaitUntilLoaded(track: AnimationTrack?, timeoutSeconds: number?): boolean
	if not track then
		return false
	end
	if self:IsLoaded(track) then
		return true
	end
	local deadline = os.clock() + math.max(0, tonumber(timeoutSeconds) or 0)
	while not self.destroyed and os.clock() < deadline do
		RunService.Heartbeat:Wait()
		if self:IsLoaded(track) then
			return true
		end
	end
	return self:IsLoaded(track)
end

function AnimationTrackCache:Prewarm(descriptors, timeoutSeconds: number?)
	if self.destroyed then
		return { total = 0, ready = 0, failed = 0, elapsed = 0 }
	end
	local startedAt = os.clock()
	local tracks = {}
	local animations = {}
	local failed = 0
	for _, descriptor in ipairs(descriptors or {}) do
		local track = self:Get(descriptor)
		local clipId = tostring(descriptor.clipId or descriptor.animationId or "")
		local entry = self.entries[clipId]
		if track and entry then
			table.insert(tracks, track)
			table.insert(animations, entry.animation)
		else
			failed += 1
		end
	end
	if #animations > 0 then
		pcall(function()
			ContentProvider:PreloadAsync(animations)
		end)
	end
	local deadline = os.clock() + math.max(0, tonumber(timeoutSeconds) or 0)
	while not self.destroyed and os.clock() < deadline do
		local allLoaded = true
		for _, track in ipairs(tracks) do
			if not self:IsLoaded(track) then
				allLoaded = false
				break
			end
		end
		if allLoaded then
			break
		end
		RunService.Heartbeat:Wait()
	end
	local ready = 0
	for _, track in ipairs(tracks) do
		if self:IsLoaded(track) then
			ready += 1
		end
	end
	return {
		total = #tracks + failed,
		ready = ready,
		failed = failed + (#tracks - ready),
		elapsed = os.clock() - startedAt,
	}
end

function AnimationTrackCache:StopAll(fadeTime: number?)
	for _, entry in pairs(self.entries) do
		if entry.track.IsPlaying then
			entry.track:Stop(fadeTime or 0.1)
		end
	end
end

function AnimationTrackCache:Destroy()
	if self.destroyed then
		return
	end
	self.destroyed = true
	self:StopAll(0)
	for _, entry in pairs(self.entries) do
		entry.track:Destroy()
		entry.animation:Destroy()
	end
	table.clear(self.entries)
end

return AnimationTrackCache

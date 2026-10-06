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

local function loadTrack(self, descriptor, key: string, nameSuffix: string): AnimationTrack?
	local animationId = tostring(descriptor.animationId or "")
	local clipId = tostring(descriptor.clipId or animationId)
	if clipId == "" or animationId == "" then
		return nil
	end
	local entry = self.entries[clipId]
	if not entry then
		entry = {}
		self.entries[clipId] = entry
	end
	local existing = entry[key]
	if existing then
		applyDescriptor(existing.track, descriptor)
		return existing.track
	end
	local animation = Instance.new("Animation")
	animation.Name = clipId .. nameSuffix
	animation.AnimationId = animationId
	local ok, trackOrError = pcall(function()
		return self.animator:LoadAnimation(animation)
	end)
	if not ok then
		animation:Destroy()
		warn(("[game1][animation] failed to load %s%s: %s"):format(clipId, nameSuffix, tostring(trackOrError)))
		return nil
	end
	local track = trackOrError :: AnimationTrack
	applyDescriptor(track, descriptor)
	entry[key] = { animation = animation, track = track }
	return track
end

function AnimationTrackCache:Get(descriptor)
	if self.destroyed or not descriptor then
		return nil
	end
	return loadTrack(self, descriptor, "primary", "")
end

function AnimationTrackCache:GetSeamCompanion(descriptor)
	if self.destroyed or not descriptor or descriptor.duplicateFirstFrameAtEnd ~= true then
		return nil
	end
	local track = loadTrack(self, descriptor, "seam", "__seam")
	if track then
		track.Looped = false
	end
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
		local primary = entry and entry.primary
		if track and primary then
			table.insert(tracks, track)
			table.insert(animations, primary.animation)
			if descriptor.duplicateFirstFrameAtEnd == true then
				local companion = self:GetSeamCompanion(descriptor)
				local updated = self.entries[clipId]
				local seam = updated and updated.seam
				if companion and seam then
					table.insert(tracks, companion)
					table.insert(animations, seam.animation)
				end
			end
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
		for _, loaded in pairs(entry) do
			if loaded.track and loaded.track.IsPlaying then
				loaded.track:Stop(fadeTime or 0.1)
			end
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
		for _, loaded in pairs(entry) do
			if loaded.track then loaded.track:Destroy() end
			if loaded.animation then loaded.animation:Destroy() end
		end
	end
	table.clear(self.entries)
end

return AnimationTrackCache

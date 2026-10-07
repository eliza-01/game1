-- Roblox Studio: StarterPlayer.StarterPlayerScripts.game1Client.MonsterAnimation.MonsterSkeletonMap (ModuleScript)
-- Pure skeleton topology helpers used by the monster locomotion compositor.
local Config = require(script.Parent:WaitForChild("MonsterAnimationCompositionConfig"))

local MonsterSkeletonMap = {}

local LOWER_NAME_TOKENS = table.freeze({
	"pelvis", "hip", "thigh", "calf", "shin", "foot", "toe", "leg", "paw", "hoof",
})

local function bonePath(bone: Bone, visual: Model): string
	local parts = { bone.Name }
	local current = bone.Parent
	while current and current ~= visual do
		table.insert(parts, 1, current.Name)
		current = current.Parent
	end
	return table.concat(parts, "/")
end

function MonsterSkeletonMap.BuildBonePathMap(visual: Model): { [string]: Bone }
	local result = {}
	for _, object in visual:GetDescendants() do
		if object:IsA("Bone") then
			result[bonePath(object, visual)] = object
		end
	end
	return result
end

local function commonAncestorPath(paths: { string }): string?
	if #paths == 0 then
		return nil
	end
	local split = {}
	for index, path in ipairs(paths) do
		split[index] = string.split(path, "/")
	end
	local common = {}
	local cursor = 1
	while true do
		local value = split[1][cursor]
		if not value then
			break
		end
		for index = 2, #split do
			if split[index][cursor] ~= value then
				return if #common > 0 then table.concat(common, "/") else nil
			end
		end
		table.insert(common, value)
		cursor += 1
	end
	return if #common > 0 then table.concat(common, "/") else nil
end

local function fallbackLowerPaths(pathMap: { [string]: Bone }): { string }
	local result = {}
	for path, bone in pathMap do
		local lowered = string.lower(bone.Name)
		for _, token in LOWER_NAME_TOKENS do
			if string.find(lowered, token, 1, true) then
				table.insert(result, path)
				break
			end
		end
	end
	table.sort(result)
	return result
end


local function parentBonePath(pathMap: { [string]: Bone }, bone: Bone, visual: Model): string?
	local parent = bone.Parent
	if parent and parent:IsA("Bone") then
		local path = bonePath(parent, visual)
		if pathMap[path] then
			return path
		end
	end
	return nil
end

function MonsterSkeletonMap.ResolveIndependentLowerBodyRoots(visual: Model, lowerPaths: { string }): { string }
	local pathMap = MonsterSkeletonMap.BuildBonePathMap(visual)
	local selected = {}
	for _, path in lowerPaths do
		if pathMap[path] then
			selected[path] = true
		end
	end

	local childrenByPath = {}
	for path in pathMap do
		childrenByPath[path] = {}
	end
	for path, bone in pathMap do
		local parentPath = parentBonePath(pathMap, bone, visual)
		if parentPath then
			table.insert(childrenByPath[parentPath], path)
		end
	end

	local pureMemo = {}
	local function isIndependentLowerSubtree(path: string): boolean
		local cached = pureMemo[path]
		if cached ~= nil then
			return cached
		end
		if not selected[path] then
			pureMemo[path] = false
			return false
		end
		for _, childPath in childrenByPath[path] or {} do
			if not isIndependentLowerSubtree(childPath) then
				pureMemo[path] = false
				return false
			end
		end
		pureMemo[path] = true
		return true
	end

	local result = {}
	for path, bone in pathMap do
		if isIndependentLowerSubtree(path) then
			local parentPath = parentBonePath(pathMap, bone, visual)
			if not parentPath or not isIndependentLowerSubtree(parentPath) then
				table.insert(result, path)
			end
		end
	end
	table.sort(result)
	return result
end

function MonsterSkeletonMap.ResolveLowerBodyPaths(visual: Model): { string }
	local pathMap = MonsterSkeletonMap.BuildBonePathMap(visual)
	local boneCount = 0
	local childrenByPath = {}
	for path, bone in pathMap do
		boneCount += 1
		childrenByPath[path] = childrenByPath[path] or {}
		local parent = bone.Parent
		if parent and parent:IsA("Bone") then
			local parentPath = bonePath(parent, visual)
			childrenByPath[parentPath] = childrenByPath[parentPath] or {}
			table.insert(childrenByPath[parentPath], path)
		end
	end
	if boneCount == 0 then
		return {}
	end

	local boundsCFrame, boundsSize = visual:GetBoundingBox()
	local minimumY = boundsCFrame.Position.Y - boundsSize.Y * 0.5
	local bandTop = minimumY + boundsSize.Y * Config.BottomLeafBandFraction
	local lowLeaves = {}
	for path, bone in pathMap do
		if #(childrenByPath[path] or {}) == 0 and bone.TransformedWorldCFrame.Position.Y <= bandTop then
			table.insert(lowLeaves, path)
		end
	end

	if #lowLeaves < 2 then
		return fallbackLowerPaths(pathMap)
	end
	local lca = commonAncestorPath(lowLeaves)
	if not lca or not pathMap[lca] then
		return fallbackLowerPaths(pathMap)
	end

	local branchRoots = {}
	local lcaDepth = #string.split(lca, "/")
	for _, leafPath in lowLeaves do
		local segments = string.split(leafPath, "/")
		if #segments > lcaDepth then
			local root = table.concat(segments, "/", 1, lcaDepth + 1)
			branchRoots[root] = true
		end
	end

	local selected = {}
	for path in pathMap do
		for branchRoot in branchRoots do
			if path == branchRoot or string.sub(path, 1, #branchRoot + 1) == branchRoot .. "/" then
				selected[path] = true
				break
			end
		end
	end

	local lcaName = string.lower(pathMap[lca].Name)
	if string.find(lcaName, "pelvis", 1, true) or string.find(lcaName, "hip", 1, true) then
		selected[lca] = true
	end

	local result = {}
	for path in selected do
		table.insert(result, path)
	end
	if #result == 0 or #result > math.floor(boneCount * Config.MaxLowerBodyFraction) then
		return fallbackLowerPaths(pathMap)
	end
	table.sort(result)
	return result
end

return table.freeze(MonsterSkeletonMap)

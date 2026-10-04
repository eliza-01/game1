local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Game1Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Game1Shared:WaitForChild("character")
local Registry = require(CharacterShared:WaitForChild("CharacterAnimationRegistry"))

local AnimationResolver = {}
local random = Random.new()

local function weightedChoice(rows)
	if type(rows) ~= "table" or #rows == 0 then
		return nil
	end
	if #rows == 1 then
		return rows[1]
	end
	local total = 0
	for _, row in ipairs(rows) do
		total += math.max(1, tonumber(row.weight) or 1)
	end
	local cursor = random:NextNumber(0, total)
	for _, row in ipairs(rows) do
		cursor -= math.max(1, tonumber(row.weight) or 1)
		if cursor <= 0 then
			return row
		end
	end
	return rows[#rows]
end

local function profileFor(character: Model)
	local profileId = tostring(character:GetAttribute("AnimationProfileId") or character:GetAttribute("CharacterArchetype") or "")
	local profile = Registry.profiles[profileId]
	if not profile then
		return nil
	end
	local expected = tostring(profile.skeletonSignature or "")
	local actual = tostring(character:GetAttribute("CharacterSkeletonSignature") or "")
	if expected ~= "" and actual ~= "" and expected ~= actual then
		warn(string.format("[game1][animation] skeleton mismatch for %s", profileId))
		return nil
	end
	return profile
end

function AnimationResolver.Resolve(character: Model, scope: string, weaponSet: string?, slot: string)
	local profile = profileFor(character)
	if not profile then
		return nil
	end
	local rows = nil
	if scope == "weapon" then
		local weapon = profile.weapons and profile.weapons[tostring(weaponSet or "")]
		rows = weapon and weapon[slot]
	else
		rows = profile.base and profile.base[slot]
	end
	return weightedChoice(rows)
end

function AnimationResolver.ListForCharacter(character: Model)
	local profile = profileFor(character)
	if not profile then
		return {}
	end
	local rows = {}
	for _, slotRows in pairs(profile.base or {}) do
		for _, row in ipairs(slotRows) do
			table.insert(rows, row)
		end
	end
	for _, weapon in pairs(profile.weapons or {}) do
		for _, slotRows in pairs(weapon) do
			for _, row in ipairs(slotRows) do
				table.insert(rows, row)
			end
		end
	end
	return rows
end

function AnimationResolver.ResolveLocomotion(character: Model, slot: string)
	local weaponSet = tostring(character:GetAttribute("AnimationWeaponSet") or "")
	if weaponSet ~= "" and weaponSet ~= "base" and weaponSet ~= "unarmed" then
		local weaponRow = AnimationResolver.Resolve(character, "weapon", weaponSet, slot)
		if weaponRow then
			return weaponRow
		end
	end
	return AnimationResolver.Resolve(character, "base", nil, slot)
end

function AnimationResolver.ResolveAction(character: Model, slot: string)
	local weaponSet = tostring(character:GetAttribute("AnimationWeaponSet") or "")
	if weaponSet ~= "" and weaponSet ~= "base" and weaponSet ~= "unarmed" then
		local weaponRow = AnimationResolver.Resolve(character, "weapon", weaponSet, slot)
		if weaponRow then
			return weaponRow
		end
	end
	return AnimationResolver.Resolve(character, "base", nil, slot)
end

return AnimationResolver

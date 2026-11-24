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
	elseif scope == "emotions" then
		rows = profile.emotions and profile.emotions[slot]
	elseif scope == "social" then
		rows = profile.social and profile.social[slot]
	else
		rows = profile.base and profile.base[slot]
	end
	if type(rows) ~= "table" or #rows == 0 then
        local shared = Registry.shared and Registry.shared[profile.family or ""]
        if shared then
            if scope == "weapon" then
                local group = shared.weapons and shared.weapons[tostring(weaponSet or "")]
                rows = group and group[slot]
            else
                local group = shared[scope == "emotions" and "emotions" or scope == "social" and "social" or "base"]
                rows = group and group[slot]
            end
        end
    end
	return weightedChoice(rows)
end

function AnimationResolver.ListForCharacter(character: Model, includeProcedural: boolean?)
	local profile = profileFor(character)
	if not profile then
		return {}
	end
	local rows = {}
	for _, slotRows in pairs(profile.emotions or {}) do
		for _, row in ipairs(slotRows) do
			if includeProcedural or tostring(row.animationId or "") ~= "" then
				table.insert(rows, row)
			end
		end
	end
	for _, slotRows in pairs(profile.social or {}) do
		for _, row in ipairs(slotRows) do
			table.insert(rows, row)
		end
	end
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
    local shared = Registry.shared and Registry.shared[profile.family or ""]
    if shared then
        for _, scope in ipairs({ "base", "emotions", "social" }) do
            for slot, candidates in pairs(shared[scope] or {}) do
                if not ((profile[scope] or {})[slot]) then
                    for _, row in ipairs(candidates) do
                        if includeProcedural or tostring(row.animationId or "") ~= "" then
                            table.insert(rows, row)
                        end
                    end
                end
            end
        end
        for weaponSet, slots in pairs(shared.weapons or {}) do
            local own = (profile.weapons or {})[weaponSet] or {}
            for slot, candidates in pairs(slots) do
                if not own[slot] then
                    for _, row in ipairs(candidates) do
                        table.insert(rows, row)
                    end
                end
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
		if weaponSet == "bow" then
			-- A bow cannot play a fallback melee clip and fire an arrow.
			return nil
		end
	end
	return AnimationResolver.Resolve(character, "base", nil, slot)
end

return AnimationResolver

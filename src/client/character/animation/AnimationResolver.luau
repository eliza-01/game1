local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Game1Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Game1Shared:WaitForChild("character")
local Registry = require(CharacterShared:WaitForChild("CharacterAnimationRegistry"))
local VariantMerge = require(CharacterShared:WaitForChild("CharacterAnimationVariantMerge"))
local GameplayFallback = require(Game1Shared:WaitForChild("combat"):WaitForChild("GameplayAttackFallback"))

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

function AnimationResolver.Resolve(character: Model, scope: string, weaponSet: string?, slot: string, variant: number?)
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
    local shared = Registry.shared and Registry.shared[profile.family or ""]
    local commonRows = nil
    if shared then
        if scope == "weapon" then
            local group = shared.weapons and shared.weapons[tostring(weaponSet or "")]
            commonRows = group and group[slot]
        else
            local group = shared[scope == "emotions" and "emotions" or scope == "social" and "social" or "base"]
            commonRows = group and group[slot]
        end
    end
    return weightedChoice(VariantMerge.Version(VariantMerge.Rows(rows, commonRows), variant))
end

function AnimationResolver.ListForCharacter(character: Model, includeProcedural: boolean?)
    local profile = profileFor(character)
    if not profile then return {} end
    local rows = {}
    local shared = Registry.shared and Registry.shared[profile.family or ""] or {}
    local function append(slotRows)
        for _, row in ipairs(slotRows or {}) do
            if includeProcedural or tostring(row.animationId or "") ~= "" then
                table.insert(rows, row)
            end
        end
    end
    for _, scope in ipairs({ "base", "emotions", "social" }) do
        local own = profile[scope] or {}
        local common = shared[scope] or {}
        local keys = {}
        for slot in pairs(own) do keys[slot] = true end
        for slot in pairs(common) do keys[slot] = true end
        for slot in pairs(keys) do append(VariantMerge.Rows(own[slot], common[slot])) end
    end
    local ownWeapons = profile.weapons or {}
    local sharedWeapons = shared.weapons or {}
    local sets = {}
    for weaponSet in pairs(ownWeapons) do sets[weaponSet] = true end
    for weaponSet in pairs(sharedWeapons) do sets[weaponSet] = true end
    for weaponSet in pairs(sets) do
        local own = ownWeapons[weaponSet] or {}
        local common = sharedWeapons[weaponSet] or {}
        local keys = {}
        for slot in pairs(own) do keys[slot] = true end
        for slot in pairs(common) do keys[slot] = true end
        for slot in pairs(keys) do append(VariantMerge.Rows(own[slot], common[slot])) end
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
		-- In GP, missing weapon attack metadata uses an explicitly labelled
		-- timing-only attack, not an unrelated base/hands clip.
		if slot == "attack" and GameplayFallback.Allowed(character) then return nil end
	end
	return AnimationResolver.Resolve(character, "base", nil, slot)
end

return AnimationResolver

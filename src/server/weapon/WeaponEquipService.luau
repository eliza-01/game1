local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local WeaponShared = Shared:WaitForChild("weapon")
local CombatShared = Shared:WaitForChild("combat")
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local WeaponRegistry = require(WeaponShared:WaitForChild("WeaponRegistry"))
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))

-- Only the Database owns gameplay stats. Asset rows supply geometry and sockets.
local function gameplayRow(slug: string, testStats: any?, upgrade: number?): any?
    local model = WeaponRegistry.weapons and WeaponRegistry.weapons[slug]
    if not model then return nil end
    local stats = testStats or Balance.WeaponForModel(slug, model.weaponType)
    if not stats then return nil end
    local row = table.clone(model)
    row.balanceId = stats.id
    local grade, requiredLevel = Balance.Grade.ForLevel(stats.level)
    row.requiredLevel = requiredLevel
    row.grade = grade
    row.weaponType = stats.type
    row.price = stats.price
    row.rarity = stats.rarity
    row.attackRadiusStuds = stats.radius
    row.meleeArcAngleDegrees = stats.arc
    row.statModifiers = {Damage = Balance.WeaponDamage(stats, upgrade or 0), AttackSpeed = stats.attackSpeedDelta, CritChance = stats.critChance - Balance.Rules.critChance}
    return row
end
local WeaponAttackMovement = require(WeaponShared:WaitForChild("WeaponAttackMovement"))
local CharacterStatsService = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterStatsService"))

local TestPolicy = require(Shared:WaitForChild("dev"):WaitForChild("GameplayTestAnimationPolicy"))
local WeaponEquipService = {}
local EQUIPPED_NAME = "EquippedWeapon"
local LEFT_EQUIPPED_NAME = "EquippedWeaponLeft"
local AnimationRegistry = require(Shared:WaitForChild("character"):WaitForChild("CharacterAnimationRegistry"))
local VariantMerge = require(Shared:WaitForChild("character"):WaitForChild("CharacterAnimationVariantMerge"))
local Timeline = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local HitPlan = require(CombatShared:WaitForChild("MeleeHitPlan"))
local function dualAnimationReady(character: Model): boolean
    local profile = AnimationRegistry.profiles[tostring(character:GetAttribute("AnimationProfileId") or character:GetAttribute("CharacterArchetype") or "")]
    if not profile then return false end
    local shared = AnimationRegistry.shared and AnimationRegistry.shared[profile.family or ""]
    local own = profile.weapons and profile.weapons.dualswords
    local common = shared and shared.weapons and shared.weapons.dualswords
    local rows = VariantMerge.Rows(own and own.attack, common and common.attack)
    if #rows == 0 then return false end
    for _, clip in ipairs(rows) do
        if not HitPlan.Resolve(Timeline.ResolveCharacterRuntime(clip.clipId, 180), true) then return false end
    end
    return true
end

local RIGHT_SOCKET_NAMES = { "weapon_grip_r", "Weapon_R_Bone", "weapon_r", "Weapon_R", "WeaponR" }
local LEFT_SOCKET_NAMES = { "weapon_grip_l", "Weapon_L_Bone", "weapon_l", "Weapon_L", "WeaponL" }
local WEAPON_GRIP_NAME = "Game1WeaponGrip"
local BoneModelMount = require(Shared:WaitForChild("rig"):WaitForChild("BoneModelMount"))

local function findByStudioPath(studioPath: string): Instance?
    if string.sub(studioPath, 1, 14) ~= "ServerStorage." then
        return nil
    end
    local node: Instance = ServerStorage
    for segment in string.gmatch(string.sub(studioPath, 15), "[^%.]+") do
        local child = node:FindFirstChild(segment)
        if not child then
            return nil
        end
        node = child
    end
    return node
end

local function findCharacterBone(character: Model, names: { string }): Bone?
    local visual = character:FindFirstChild("Visual") or character:FindFirstChild("ImportedRig") or character
    for _, name in ipairs(names) do
        local found = visual:FindFirstChild(name, true)
        if found and found:IsA("Bone") then
            return found
        end
    end
    return nil
end

local function socketNames(weaponType: string): { string }
    local kind = string.lower(weaponType)
    return if kind == "bow" or kind == "bigsword" then LEFT_SOCKET_NAMES else RIGHT_SOCKET_NAMES
end

local function weaponReferencePart(model: Model): BasePart?
    if model.PrimaryPart then
        return model.PrimaryPart
    end
    local parts = {}
    for _, descendant in model:GetDescendants() do
        if descendant:IsA("BasePart") then
            table.insert(parts, descendant)
        end
    end
    table.sort(parts, function(left, right)
        return left:GetFullName() < right:GetFullName()
    end)
    return parts[1]
end

local function ensureCanonicalRuntimeGrip(model: Model): Attachment?
    -- Runtime owns the grip contract. Studio templates may be old, may contain a
    -- stale per-weapon rotated grip, or may contain no grip at all. Preserve only
    -- the authored grip POINT; never inherit a template/model pivot orientation.
    local staleGrips = {}
    for _, descendant in model:GetDescendants() do
        if descendant:IsA("Attachment") and descendant.Name == WEAPON_GRIP_NAME then
            table.insert(staleGrips, descendant)
        end
    end
    table.sort(staleGrips, function(left, right)
        return left:GetFullName() < right:GetFullName()
    end)

    local gripPoint = model:GetPivot().Position
    if staleGrips[1] then
        gripPoint = staleGrips[1].WorldPosition
    end
    for _, grip in staleGrips do
        grip:Destroy()
    end

    local referencePart = weaponReferencePart(model)
    if not referencePart then
        return nil
    end

    -- World XYZ is the one canonical authored basis for every weapon. The local
    -- Attachment CFrame stores the inverse of whatever hidden part/model basis
    -- Roblox imported, so all weapons enter the equip solver identically.
    local grip = BoneModelMount.CreateGrip(referencePart, WEAPON_GRIP_NAME, gripPoint)
    grip:SetAttribute("Game1WeaponGrip", true)
    return grip
end

local function prepareWeapon(model: Model)
    for _, descendant in model:GetDescendants() do
        if descendant:IsA("Humanoid") or descendant:IsA("AnimationController") then
            descendant:Destroy()
        elseif descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
            descendant.Massless = true
        end
    end
end

local function clearWeapon(character: Model)
    for _, name in ipairs({EQUIPPED_NAME, LEFT_EQUIPPED_NAME}) do
        local old = character:FindFirstChild(name)
        if old then old:Destroy() end
    end
end

local function attackRadiusFor(row: any?): number
    local value = tonumber(row and row.attackRadiusStuds) or AttackConfig.Range
    return math.clamp(value, 1, AttackConfig.MaxAimDistance)
end

local function meleeArcFor(row: any?): number
    return math.clamp(tonumber(row and row.meleeArcAngleDegrees) or AttackConfig.MeleeDefaultArcAngle, 1, 360)
end

local function purgeLegacyWeaponBox(weapon: Model)
    -- Retired M27–M357 attributes are never used by combat or the client.
    for _, name in ipairs({"WeaponAttackBoxLocalCFrame", "WeaponAttackBoxSize", "WeaponAttackBoneBoxLocalPosition"}) do
        weapon:SetAttribute(name, nil)
    end
end

function WeaponEquipService.Unequip(character: Model)
    clearWeapon(character)
    character:SetAttribute("EquippedWeaponBalanceId", "")
    character:SetAttribute("EquippedWeaponRequiredLevel", nil)
    character:SetAttribute("EquippedWeaponGrade", nil)
    character:SetAttribute("EquippedWeaponSlug", "")
    character:SetAttribute("EquippedWeaponType", "")
    character:SetAttribute("EquippedWeaponRarity", "")
    character:SetAttribute("AttackRadius", attackRadiusFor(nil))
    character:SetAttribute("MeleeArcAngle", meleeArcFor(nil))
    character:SetAttribute("AnimationWeaponSet", "hands")
    character:SetAttribute("AttackMovementLocomotionMode", "Run")
    character:SetAttribute("AttackMovementRunSpeedMultiplier", 1)
    CharacterStatsService.ApplyModifiers(character, {})
end

function WeaponEquipService.Equip(character: Model, slugValue: any, testId: string?, upgrade: number?): (boolean, string?)
    local slug = string.lower(tostring(slugValue or ""))
    local row = gameplayRow(slug)
    if testId then
        if not TestPolicy.IsMaleTest(character) then return false, "Test override denied" end
        local stats = Balance.Weapon(testId)
        local model = WeaponRegistry.weapons[slug]
        if not stats or not model or (model.weaponType ~= stats.type and not (stats.type == "dualswords" and model.weaponType == "sword")) then
            return false, "Incompatible test model"
        end
        row = gameplayRow(slug, stats, upgrade)
    end
    if not row then
        return false, "weapon model has no compatible Database binding: " .. slug
    end

    local isDual = row.weaponType == "dualswords"
    local dualReady = isDual and dualAnimationReady(character)
    if isDual and (tonumber(character:GetAttribute("Level")) or 1) < row.requiredLevel then
        return false, "Dualswords require LVL " .. row.requiredLevel
    end
    if isDual and not dualReady and not testId then return false, "Publish dualswords animations and two hit timings first" end
    local template = findByStudioPath(tostring(row.serverStoragePath or ""))
    if not template or not template:IsA("Model") then
        WeaponEquipService.Unequip(character)
        return false, "weapon template is not synced into ServerStorage: " .. slug
    end

    local targetBone = findCharacterBone(character, socketNames(tostring(row.weaponType or "")))
    if not targetBone then
        WeaponEquipService.Unequip(character)
        return false, "character has no compatible weapon socket bone"
    end

    local leftBone = if isDual then findCharacterBone(character, LEFT_SOCKET_NAMES) else nil
    if isDual and not leftBone then return false, "Dualswords require both hand sockets" end
    clearWeapon(character)
    local weapon = template:Clone()
    weapon.Name = EQUIPPED_NAME
    prepareWeapon(weapon)
    local grip = ensureCanonicalRuntimeGrip(weapon)
    if not grip then
        WeaponEquipService.Unequip(character)
        return false, "weapon model contains no BasePart for runtime grip"
    end

    weapon:SetAttribute("Game1WeaponAttachment", true)
    weapon:SetAttribute("WeaponTargetBoneName", targetBone.Name)
    weapon:SetAttribute("WeaponSlug", slug)
    weapon:SetAttribute("WeaponType", tostring(row.weaponType or ""))
    weapon:SetAttribute("WeaponRarity", tostring(row.rarity or ""))
    weapon:SetAttribute("AttackRadius", attackRadiusFor(row))
    weapon:SetAttribute("MeleeArcAngle", meleeArcFor(row))
    weapon:SetAttribute("Game1WeaponGripRotation", nil)
    weapon:SetAttribute("WeaponAttachmentMode", "runtime-canonical-grip-v2")
    BoneModelMount.Place(weapon, grip, BoneModelMount.SocketFrame(targetBone, "weapon"))
    purgeLegacyWeaponBox(weapon)
    weapon.Parent = character
    if isDual and leftBone then
        local left = weapon:Clone()
        left.Name = LEFT_EQUIPPED_NAME
        left:SetAttribute("WeaponTargetBoneName", leftBone.Name)
        left:SetAttribute("WeaponHand", "left")
        local leftGrip = left:FindFirstChild(WEAPON_GRIP_NAME, true)
        if not leftGrip or not leftGrip:IsA("Attachment") then left:Destroy(); WeaponEquipService.Unequip(character); return false, "Dualswords left grip missing" end
        BoneModelMount.Place(left, leftGrip, BoneModelMount.SocketFrame(leftBone, "weapon"))
        left.Parent = character
    end

    character:SetAttribute("EquippedWeaponBalanceId", row.balanceId)
    character:SetAttribute("EquippedWeaponRequiredLevel", row.requiredLevel)
    character:SetAttribute("EquippedWeaponGrade", row.grade)
    character:SetAttribute("EquippedWeaponSlug", slug)
    character:SetAttribute("EquippedWeaponType", tostring(row.weaponType or ""))
    character:SetAttribute("EquippedWeaponRarity", tostring(row.rarity or ""))
    local attackMovement = WeaponAttackMovement.Resolve(row.weaponType)
    character:SetAttribute("AttackRadius", attackRadiusFor(row))
    character:SetAttribute("MeleeArcAngle", meleeArcFor(row))
    character:SetAttribute("AnimationWeaponSet", if isDual then "dualswords" else attackMovement.animationSet)
    character:SetAttribute("AttackMovementLocomotionMode", attackMovement.locomotionMode)
    character:SetAttribute("AttackMovementRunSpeedMultiplier", attackMovement.runSpeedMultiplier)
    CharacterStatsService.ApplyModifiers(character, row.statModifiers or {})
    return true, nil
end

-- Common actor equipment entry point: NPCs call this without player-only stats.
-- Reuses the runtime grip and bone solver of Equip(); weapon OBBs are legacy.
function WeaponEquipService.EquipVisual(actor: Model, slugValue: any, hand: string, modelName: string): (Model?, any?, string?)
    local slug = string.lower(tostring(slugValue or ""))
    local row = gameplayRow(slug) or (WeaponRegistry.weapons and WeaponRegistry.weapons[slug])
    if not row or row.status ~= "PUBLISHED" then
        return nil, row, "weapon not registered/published: " .. slug
    end
    local template = findByStudioPath(tostring(row.serverStoragePath or ""))
    if not template or not template:IsA("Model") then
        return nil, row, "weapon is not synced to ServerStorage: " .. slug
    end
    local names = if hand == "right" then RIGHT_SOCKET_NAMES else if hand == "left" then LEFT_SOCKET_NAMES else nil
    if not names then return nil, row, "invalid hand: " .. hand end
    local bone = findCharacterBone(actor, names)
    if not bone then return nil, row, "NPC has no " .. hand .. " weapon socket" end
    local weapon = template:Clone()
    weapon.Name = modelName
    prepareWeapon(weapon)
    local grip = ensureCanonicalRuntimeGrip(weapon)
    if not grip then weapon:Destroy(); return nil, row, "weapon has no grip BasePart" end
    weapon:SetAttribute("Game1WeaponAttachment", true)
    weapon:SetAttribute("WeaponTargetBoneName", bone.Name)
    weapon:SetAttribute("WeaponHand", hand)
    weapon:SetAttribute("WeaponSlug", slug)
    weapon:SetAttribute("WeaponType", tostring(row.weaponType or ""))
    weapon:SetAttribute("WeaponRarity", tostring(row.rarity or ""))
    weapon:SetAttribute("AttackRadius", attackRadiusFor(row))
    weapon:SetAttribute("MeleeArcAngle", meleeArcFor(row))
    weapon:SetAttribute("Game1WeaponGripRotation", nil)
    weapon:SetAttribute("WeaponAttachmentMode", "runtime-canonical-grip-v2")
    BoneModelMount.Place(weapon, grip, BoneModelMount.SocketFrame(bone, "weapon"))
    purgeLegacyWeaponBox(weapon)
    weapon.Parent = actor
    return weapon, row, nil
end

function WeaponEquipService.GetAvailable(slugValue: any): any?
    local slug = string.lower(tostring(slugValue or ""))
    if slug == "" then
        return nil
    end
    return gameplayRow(slug)
end

function WeaponEquipService.ListAvailable(): { any }
    local rows = {}
    for slug in pairs(WeaponRegistry.weapons or {}) do
        local row = gameplayRow(slug)
        if row and tonumber(row.modelAssetId) then
            table.insert(rows, {
                slug = tostring(slug),
                nameEn = tostring(row.nameEn or slug),
                nameRu = tostring(row.nameRu or ""),
                weaponType = tostring(row.weaponType or ""),
                animationSet = WeaponAttackMovement.AnimationSetForType(row.weaponType),
                rarity = tostring(row.rarity or ""),
                attackRadiusStuds = attackRadiusFor(row),
                meleeArcAngleDegrees = meleeArcFor(row),
                modelAssetId = tostring(row.modelAssetId or ""),
            })
        end
    end
    table.sort(rows, function(left, right)
        if left.weaponType == right.weaponType then
            return left.nameEn < right.nameEn
        end
        return left.weaponType < right.weaponType
    end)
    return rows
end

function WeaponEquipService.TestModel(weaponType: string): (string?, boolean)
    -- GP must use the real 2hs model and the requested pair of identical swords.
    if weaponType == "bigsword" or weaponType == "dualswords" then
        local slug = if weaponType == "bigsword" then "newbie_slayer_01" else "newbie_sword_01"
        local expected = if weaponType == "bigsword" then "bigsword" else "sword"
        local row = WeaponRegistry.weapons[slug]
        local model = row and row.weaponType == expected and tonumber(row.modelAssetId)
            and findByStudioPath(tostring(row.serverStoragePath or ""))
        if model and model:IsA("Model") then return slug, false end
        return nil, false
    end
    local preferred = {sword="newbie_sword_01", dagger="newbie_dagger", bow="newbie_bow"}
    local candidates = {}
    for slug, row in pairs(WeaponRegistry.weapons or {}) do
        if row.weaponType == weaponType and tonumber(row.modelAssetId) then table.insert(candidates, slug) end
    end
    table.sort(candidates)
    if preferred[weaponType] then table.insert(candidates, 1, preferred[weaponType]) end
    for _, slug in ipairs(candidates) do
        local row = WeaponRegistry.weapons[slug]
        local model = row and findByStudioPath(tostring(row.serverStoragePath or ""))
        if model and model:IsA("Model") then return slug, false end
    end
    return nil, false
end

-- Purely visual Studio showcase: no combat, sockets, or stats on the stand.
function WeaponEquipService.CloneTestDisplay(weaponType: string): Model?
    local slug = WeaponEquipService.TestModel(weaponType)
    local row = slug and WeaponRegistry.weapons[slug]
    local template = row and findByStudioPath(tostring(row.serverStoragePath or ""))
    if not template or not template:IsA("Model") then return nil end
    local model = template:Clone()
    prepareWeapon(model)
    if weaponType == "dualswords" then
        local pair = Instance.new("Model")
        model.Parent = pair
        local second = model:Clone()
        local _, bounds = model:GetBoundingBox()
        second:PivotTo(model:GetPivot() * CFrame.new(math.max(1, bounds.X + 0.5), 0, 0))
        second.Parent = pair
        return pair
    end
    return model
end

function WeaponEquipService.EquipStartup(character: Model)
    local player = game:GetService("Players"):GetPlayerFromCharacter(character)
    -- A playtest choice survives respawn in this session; never read a
    -- Studio Test Loadout value as implicit ownership in the live game.
    local selected = player and player:GetAttribute("Game1PlaytestWeaponChosen") == true
    local slug = if selected then tostring(player:GetAttribute("SelectedWeaponSlug") or "")
        else tostring(WeaponRegistry.activeWeaponSlug or "")
    character:SetAttribute("WeaponLoadoutSource", if selected then "playtest-selector" else "startup")
    if slug == "" then
        WeaponEquipService.Unequip(character)
        return
    end
    local row = gameplayRow(slug)
    if not row or (not selected and row.requiredLevel > (tonumber(character:GetAttribute("Level")) or 1)) then
        WeaponEquipService.Unequip(character)
        warn("[game1][weapon] startup requires a compatible, level-eligible Database binding: " .. slug)
        return
    end
    local ok, reason = WeaponEquipService.Equip(character, slug)
    if not ok then
        warn("[game1][weapon] " .. tostring(reason))
    else
        print(("[game1][weapon] startup loadout equipped %s"):format(slug))
    end
end

return table.freeze(WeaponEquipService)

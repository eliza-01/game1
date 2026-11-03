-- Character-only attack cadence policy. Gameplay duration is determined by the
-- authoritative AttackSpeed stat, never by the authored animation clip length.
-- NPC/monster cadence is intentionally separate.
local CharacterAttackCadence = {}

-- Matches the historical 1.5s male 1HS clip at 50% playback (AttackSpeed 100).
-- Doubling AttackSpeed doubles attacks per second; one cadence for every clip.
CharacterAttackCadence.ReferenceAttackSpeed = 100
CharacterAttackCadence.ReferenceDurationSeconds = 3.0
CharacterAttackCadence.MinAttackSpeed = 25
CharacterAttackCadence.MaxAttackSpeed = 400

function CharacterAttackCadence.NormalizeAttackSpeed(value: any): number
    local numeric = tonumber(value)
    if numeric == nil or numeric ~= numeric or numeric == math.huge or numeric == -math.huge then
        numeric = CharacterAttackCadence.ReferenceAttackSpeed
    end
    return math.clamp(numeric, CharacterAttackCadence.MinAttackSpeed, CharacterAttackCadence.MaxAttackSpeed)
end

function CharacterAttackCadence.DurationForStat(attackSpeed: any): number
    local normalized = CharacterAttackCadence.NormalizeAttackSpeed(attackSpeed)
    return CharacterAttackCadence.ReferenceDurationSeconds
        * CharacterAttackCadence.ReferenceAttackSpeed / normalized
end

return table.freeze(CharacterAttackCadence)

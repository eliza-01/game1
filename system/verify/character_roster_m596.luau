-- Run from repository root with Luau CLI; pure roster semantics, no live DataStore.
local Roster = require("../../src/server/character/CharacterProfileRoster")
local legacy = {schemaVersion = 1, archetype = "human_male", appearance = {hair = "original"}, xp = 321, gold = 42, lastWorldCFrame = {1,2,3,1,0,0,0,1,0,0,0,1}}
local original = assert(Roster.Decode(legacy))
assert(original.selectedId == "legacy" and #original.characters == 1)
assert(original.characters[1].xp == 321 and original.characters[1].gold == 42)
assert(Roster.Equal(original.characters[1].lastWorldCFrame, legacy.lastWorldCFrame))
assert(Roster.Matches(legacy, Roster.Copy(legacy)))
assert(not Roster.Matches({schemaVersion=1}, legacy))
local two = assert(Roster.Append(original, "two", "human_male", {hair = "different"}))
assert(two.selectedId == "two" and #two.characters == 2 and #original.characters == 1)
assert(two.characters[2].xp == 0 and two.characters[2].gold == 0 and two.characters[2].lastWorldCFrame == nil)
two.characters[2].xp = 17
assert(two.characters[1].xp == 321)
assert(two.characters[1].appearance.hair == "original")
assert(two.characters[2].appearance.hair == "different")
assert(not Roster.Append(two, "two", "human_female", {}))
assert(not Roster.Remove(two, "foreign"))
local one = assert(Roster.Remove(two, "two"))
assert(one.selectedId == "legacy" and #one.characters == 1 and one.characters[1].xp == 321)
local empty = assert(Roster.Remove(one, "legacy"))
assert(#empty.characters == 0 and empty.selectedId == nil)
empty.revision = "delete-1"
assert(Roster.Decode(empty))
assert(not Roster.Matches(empty, legacy))
local new = assert(Roster.Append(empty, "new", "human_female", {}))
for i = 2, Roster.Limit do new = assert(Roster.Append(new, tostring(i), "human_female", {})) end
assert(not Roster.Append(new, "overflow", "human_male", {}))
new.revision = "new-2"
assert(Roster.Decode(new))
assert(not Roster.Matches(new, empty))
assert(Roster.Matches(new, Roster.Copy(new)))
local duplicate = Roster.Copy(new)
duplicate.characters[2].id = duplicate.characters[1].id
assert(not Roster.Decode(duplicate))
assert(not Roster.Decode({schemaVersion = 99}))
assert(not Roster.Decode({schemaVersion=1, archetype="unknown", appearance={}}))
assert(Roster.Decode(nil))
print("M596 roster: migration, independent progress, capacity, delete/recreate and revision guards passed")

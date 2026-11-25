-- Studio Play, Server Command Bar. Does not write profiles or change the Place.
local Shared = game:GetService("ReplicatedStorage").Game1Shared
local Appearance = require(game:GetService("ServerScriptService").Game1Server.character.CharacterCreationAppearanceService)
local Materials = require(Shared.character.CharacterCreationMaterials)
local list = {"Plastic", "Slate", "Fabric", "SmoothPlastic", "Sandstone", "Grass", "LeafyGrass", "Concrete"}
for _, id in {"human_male", "human_female"} do
    for _, material in list do
        assert(Enum.Material[material])
        local choice = {materials = {hair = material, eyes = material, eyebrows = material, head = material}}
        local recipe, checked, reason = Appearance.Resolve(id, choice)
        assert(recipe and checked, reason)
        for _, slot in {"hair", "head", "eye_l", "eye_r", "eyebrow_l", "eyebrow_r"} do
            assert(recipe.parts[slot].material == material, id .. ": " .. slot)
        end
        for _, group in Materials.Groups do assert(checked.materials[group] == material) end
        local roundtrip = Appearance.Resolve(id, checked)
        assert(roundtrip)
    end
    local recipe, checked = Appearance.Resolve(id, {materials = {hair = "Sand", eyes = "Metal"}}, true)
    assert(recipe and checked and checked.materials.hair == "Plastic" and checked.materials.eyes == "Plastic")
    local invalid, _, reason = Appearance.Resolve(id, {materials = {hair = "Sand"}})
    assert(not invalid and reason == "invalid_hair_material")
end
print("[game1][m493] face material recipes, saved-profile migration and validation OK")

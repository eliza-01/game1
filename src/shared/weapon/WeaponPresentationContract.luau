-- Replicated presentation only; equipment ownership and socket attachment are separate.
-- Keep this shared contract independent of NPC names, animation names and weapon types.
return table.freeze({
    HiddenAttribute = "NpcWeaponDisarmed", -- existing M67 network contract
})

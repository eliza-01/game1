--!strict
-- Only server-trusted, published, rig-compatible face/hair recipes may reach Builder.
-- This module owns selection validation; gameplay/preview share the same recipe.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local FaceMaterials = require(Shared:WaitForChild("character"):WaitForChild("CharacterCreationMaterials"))
local AppearanceRegistry = require(Shared:WaitForChild("character"):WaitForChild("CharacterCreationAppearanceRegistry"))
local EyeColors = require(Shared:WaitForChild("character"):WaitForChild("CharacterCreationEyeColors"))
local GameOptions = require(Shared:WaitForChild("GameOptions"))
local Service = {}
local OPTIONS = {hair = true, head = true, eyes = true, eyebrows = true}
local COLORS = {hair = true, eyes = true, eyebrows = true}

local function archetypeRow(id: string): any?
    local characters = require(Shared:WaitForChild("character"):WaitForChild("CharacterRegistry"))
    for _, row in ipairs(characters.archetypes or {}) do
        if row.id == id and row.status == "ASSEMBLY_READY" and row.assembly and row.assembly.ready == true then
            return row
        end
    end
    return nil
end

local function choice(entries: any, selected: any, fallback: any): any?
    local requested = if selected == nil then fallback else selected
    if type(requested) ~= "string" then return nil end
    for _, entry in ipairs(entries or {}) do
        if entry.id == requested then return entry end
    end
    return nil
end

local asColor = EyeColors.Parse

local function defaultId(entries: any, slot: string): string
    local default = if slot == "eyes" then "eye_l" elseif slot == "eyebrows" then "eyebrow_l" else slot
    local id = (entries and entries[default] and entries[default].id) or ""
    if slot == "eyes" or slot == "eyebrows" then id = string.gsub(id, "_[lr]$", "") end
    return id
end

function Service.Resolve(archetype: any, values: any, savedProfile: boolean?): (any?, any?, string?)
    if type(archetype) ~= "string" or (archetype ~= "human_male" and archetype ~= "human_female") then
        return nil, nil, "invalid_archetype"
    end
    if values ~= nil and type(values) ~= "table" then return nil, nil, "invalid_appearance" end
    values = values or {}
    for key in pairs(values) do
        if not OPTIONS[key] and key ~= "colors" and key ~= "materials" then return nil, nil, "unknown_appearance_field" end
    end
    local row = archetypeRow(archetype)
    local catalog = (AppearanceRegistry.archetypes or {})[archetype]
    if not row or not catalog then return nil, nil, "appearance_unavailable" end
    local selected = {}
    local chosen = {}
    for _, option in ipairs({"hair", "head", "eyes", "eyebrows"}) do
        local fallback = defaultId(row.assembly.parts, option)
        if fallback == "" and catalog[option] and catalog[option][1] then fallback = catalog[option][1].id end
        local item = choice(catalog[option], values[option], fallback)
        if not item then return nil, nil, "unknown_" .. option end
        chosen[option] = item
        selected[option] = item.id
    end
    local colors = if values.colors == nil then {} else values.colors
    if type(colors) ~= "table" then return nil, nil, "invalid_colors" end
    for key in pairs(colors) do if not COLORS[key] then return nil, nil, "unknown_color_channel" end end
    local eyes = EyeColors.Normalize(colors.eyes, EyeColors.Defaults(row.assembly.parts))
    if not eyes then return nil, nil, "invalid_eyes_color" end
    local safeColors: any = {eyes = eyes}
    if colors.eyebrows ~= nil then
        local parsed = asColor(colors.eyebrows)
        if not parsed then return nil, nil, "invalid_eyebrows_color" end
        safeColors.eyebrows = parsed
    end
    local hairColors = if colors.hair == nil then {} else colors.hair
    if type(hairColors) ~= "table" then return nil, nil, "invalid_hair_colors" end
    local channels = {}
    for _, name in ipairs(chosen.hair.part.colorChannels or {}) do channels[name] = true end
    safeColors.hair = {}
    for channel, raw in pairs(hairColors) do
        if not channels[channel] then return nil, nil, "unknown_hair_channel" end
        local parsed = asColor(raw)
        if not parsed then return nil, nil, "invalid_hair_color" end
        safeColors.hair[channel] = parsed
    end
    selected.colors = safeColors
    local provided = if values.materials == nil then {} else values.materials
    if type(provided) ~= "table" then return nil, nil, "invalid_materials" end
    for key in pairs(provided) do
        if type(key) ~= "string" or not FaceMaterials.Slot(key) then return nil, nil, "unknown_material_channel" end
    end
    local allowed = GameOptions.CharacterCreationSettings().materialChoices or {}
    local selectedMaterials = {}
    for _, group in ipairs(FaceMaterials.Groups) do
        local slot = FaceMaterials.Slot(group) :: string
        local choices = allowed[group] or {"Plastic"}
        local material = provided[group]
        if material == nil then
            local inherited = (row.assembly.parts[slot] or {}).material or "Plastic"
            material = if table.find(choices, inherited) then inherited else "Plastic"
        end
        -- Older saved profiles may contain retired materials. Never allow an
        -- untrusted new selection to use this compatibility path.
        if savedProfile and type(material) == "string" and not table.find(choices, material) then
            material = "Plastic"
        end
        if type(material) ~= "string" or not table.find(choices, material) or Enum.Material[material] == nil then
            return nil, nil, "invalid_" .. group .. "_material"
        end
        selectedMaterials[group] = material
    end
    selected.materials = selectedMaterials

    local recipe = table.clone(row.assembly)
    recipe.parts = table.clone(row.assembly.parts)
    for _, slot in ipairs({"hair", "head"}) do
        -- Preserve the authored atlas for the head; it is not a color-only slot.
        recipe.parts[slot] = if slot == "head" and selected.head == (row.assembly.parts.head or {}).id
            then table.clone(row.assembly.parts.head) else table.clone(chosen[slot].part)
        recipe.parts[slot].material = selectedMaterials[slot]
    end
    for _, group in ipairs({"eyes", "eyebrows"}) do
        local item = chosen[group]
        for _, side in ipairs({"l", "r"}) do
            local slot = if group == "eyes" then "eye_" .. side else "eyebrow_" .. side
            recipe.parts[slot] = table.clone(if side == "l" then item.left else item.right)
            recipe.parts[slot].material = if group == "eyes" then selectedMaterials.eyes else selectedMaterials.eyebrows
            if group == "eyes" then recipe.parts[slot].color = eyes[side]
            elseif safeColors.eyebrows then recipe.parts[slot].color = safeColors.eyebrows
            else recipe.parts[slot].color = (row.assembly.parts[slot] or {}).color or "#000000" end
        end
    end
    recipe.parts.hair.material = selectedMaterials.hair
    recipe.parts.hair.colors = table.clone(safeColors.hair)
    if next(safeColors.hair) == nil then
        recipe.parts.hair.colors = table.clone((row.assembly.parts.hair or {}).colors or {})
        -- Different styles have different channel names; retain only authored channels.
        for channel in pairs(recipe.parts.hair.colors) do
            if not channels[channel] then recipe.parts.hair.colors[channel] = nil end
        end
    end
    return recipe, selected, nil
end

-- Build templates are keyed only by geometry choices, never arbitrary color data.
function Service.VisualKey(archetype: string, selected: any): string
    return table.concat({archetype, selected.head, selected.hair, selected.eyes, selected.eyebrows}, "|")
end

return table.freeze(Service)

-- Mobile equipment shortcuts, not a debug panel. The existing service owns authorization/equip.
local Slots = require(script.Parent:WaitForChild("MobileWeaponSlots"))
local Catalog = require(script.Parent:WaitForChild("WeaponSlotCatalog"))
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local Quick = {}
function Quick.Mount(gui, player, getCatalog, selectWeapon)
    local rows = nil
    local busy = false
    local preferred = {}
    local character = nil
    local connection = nil
    local function ready()
        return character ~= nil and character == player.Character
            and character:GetAttribute("LifeState") == "Alive"
            and player:GetAttribute("Game1GameplayTestActive") ~= true
            and not UiInputGuard.IsWorldSuspended()
    end
    local slots = Slots.Create(gui, function(kind)
        if busy or not ready() or character:GetAttribute("EquippedWeaponType") == kind then return end
        local original = character
        busy = true
        task.spawn(function()
            local ok, err = pcall(function()
                if not rows then
                    local result = getCatalog()
                    if type(result) ~= "table" or result.enabled ~= true or type(result.weapons) ~= "table" then
                        return
                    end
                    rows = result.weapons
                    local currentKind = character and character:GetAttribute("EquippedWeaponType")
                    local currentSlug = character and character:GetAttribute("EquippedWeaponSlug")
                    if currentKind and currentSlug and Catalog.Pick(rows, currentKind, currentSlug) == currentSlug then
                        preferred[currentKind] = currentSlug
                    end
                end
                -- The RPC may yield across respawn or a modal opening.
                if character ~= original or not ready() then return end
                local slug = Catalog.Pick(rows, kind, preferred[kind])
                if not slug then
                    -- Refresh on the next tap instead of permanently caching a missing category.
                    rows = nil
                    warn("[game1][weapon-slot] no available weapon for type: " .. tostring(kind))
                    return
                end
                local result = selectWeapon(slug)
                if type(result) == "table" and result.ok == true then
                    if character == original then preferred[kind] = slug end
                else
                    warn("[game1][weapon-slot] selection rejected: " .. tostring(type(result) == "table" and result.error or "no response"))
                end
            end)
            busy = false
            if not ok then warn("[game1][weapon-slot] " .. tostring(err)) end
        end)
    end)
    local function refresh()
        local kind = character and character:GetAttribute("EquippedWeaponType")
        local slug = character and character:GetAttribute("EquippedWeaponSlug")
        if rows and type(kind) == "string" and type(slug) == "string"
            and Catalog.Pick(rows, kind, slug) == slug then
            preferred[kind] = slug
        end
        slots.SetSelected(kind)
        slots.SetVisible(ready())
    end
    local function bind(model)
        if connection then connection:Disconnect(); connection = nil end
        character = model
        if model then
            connection = model.AttributeChanged:Connect(function(name)
                if name == "EquippedWeaponType" or name == "EquippedWeaponSlug" or name == "LifeState" then refresh() end
            end)
        end
        refresh()
    end
    player.CharacterAdded:Connect(bind)
    player.CharacterRemoving:Connect(function(model) if character == model then bind(nil) end end)
    player:GetAttributeChangedSignal("Game1GameplayTestActive"):Connect(refresh)
    gui.Parent:GetAttributeChangedSignal("Game1CharacterSceneInputBlocked"):Connect(refresh)
    gui.Parent:GetAttributeChangedSignal("Game1SettingsInputBlocked"):Connect(refresh)
    gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(slots.Layout)
    bind(player.Character)
end
return table.freeze(Quick)

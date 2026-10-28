--!strict
-- Runtime state of a removable padlock. A real inventory/key service may
-- replace HasKey later; no client authority and no database mutation here.
local RunService = game:GetService("RunService")
local Padlock = {}
-- Studio-only test attribute. Never trust client writes or use as persisted inventory.
Padlock.TestKeyAttribute = "Game1HouseTestKeyOwned"
local ATTRIBUTE = "Game1PadlockAttached"

function Padlock.Ensure(house: Model, hasSocket: boolean)
    if not hasSocket then return end
    if typeof(house:GetAttribute(ATTRIBUTE)) ~= "boolean" then
        house:SetAttribute(ATTRIBUTE, true)
    end
end

function Padlock.IsAttached(house: Model, hasSocket: boolean): boolean
    return hasSocket and house:GetAttribute(ATTRIBUTE) == true
end

function Padlock.HasKey(player: Player): boolean
    -- Outside Studio the stub always grants access. Debug service is the only
    -- writer of this replicated attribute while testing in Studio.
    return not RunService:IsStudio() or player:GetAttribute(Padlock.TestKeyAttribute) ~= false
end

function Padlock.SetTestKey(player: Player, owned: boolean): boolean
    if not RunService:IsStudio() then return false end
    player:SetAttribute(Padlock.TestKeyAttribute, owned)
    return true
end

function Padlock.CanAttach(house: Model, hasSocket: boolean, doorOpen: boolean, doorMoving: boolean): boolean
    return hasSocket and not Padlock.IsAttached(house, hasSocket) and not doorOpen and not doorMoving
end

function Padlock.Toggle(house: Model, player: Player, hasSocket: boolean, doorOpen: boolean, doorMoving: boolean): (boolean, string)
    if not hasSocket then return false, "В доме нет навесного замка" end
    if not Padlock.HasKey(player) then return false, "Нужен ключ" end
    if Padlock.IsAttached(house, true) then
        house:SetAttribute(ATTRIBUTE, false)
        return true, "Замок снят · дверь разблокирована"
    end
    if not Padlock.CanAttach(house, hasSocket, doorOpen, doorMoving) then
        return false, "Нельзя навесить замок на открытую или движущуюся дверь"
    end
    house:SetAttribute(ATTRIBUTE, true)
    return true, "Замок навешен · дверь заперта"
end

return table.freeze(Padlock)

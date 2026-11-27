--!strict
-- Selection-only account roster operations. All calls share Gateway's request lock.
local Balance = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("balance"):WaitForChild("Balance"))
local RosterGateway = {}
function RosterGateway.Publish(gateway: any, player: Player)
    local record = gateway.profiles.Get(player)
    local list = gateway.profiles.List(player)
    player:SetAttribute("CharacterRosterCount", #list)
    local xp = Balance.NormalizeXP(if record then record.xp else 0)
    player:SetAttribute("CharacterXP", xp)
    player:SetAttribute("CharacterGold", Balance.NormalizeGold(if record then record.gold else 0))
    player:SetAttribute("CharacterLevel", Balance.LevelForXP(xp))
    player:SetAttribute("CharacterProfileArchetype", if record then record.archetype else "")
end
function RosterGateway.Read(gateway: any, player: Player, id: any): any
    if not gateway.enabled or not gateway.pending[player] or player:GetAttribute("CharacterCreationStatus") ~= "selection" then
        return {ok = false, error = "selection_not_pending"}
    end
    if not gateway.profiles.Ready(player) then return {ok = false, error = "profile_reload_required"} end
    if id ~= nil and (type(id) ~= "string" or not gateway.profiles.Select(player, id)) then
        return {ok = false, error = "character_unavailable"}
    end
    local record = gateway.profiles.Get(player)
    if not record then return {ok = false, error = "character_unavailable"} end
    local list, selectedId = gateway.profiles.List(player)
    local checked, problem = gateway.validate(record.archetype, record.appearance, true)
    if checked then gateway.profiles.SetValidatedAppearance(player, checked) end
    RosterGateway.Publish(gateway, player)
    -- An invalid preview/appearance must not prevent deleting a broken slot.
    return {ok = true, characters = list, selectedId = selectedId, limit = gateway.profiles.Limit,
        archetype = record.archetype, appearance = checked, appearanceError = problem}
end
function RosterGateway.Change(gateway: any, player: Player, action: any, id: any): any
    if not gateway.enabled or not gateway.pending[player] then return {ok = false, error = "creation_not_pending"} end
    if not gateway.profiles.Ready(player) then return {ok = false, error = "profile_reload_required"} end
    local stage = player:GetAttribute("CharacterCreationStatus")
    local list, selectedId = gateway.profiles.List(player)
    if action == "cancel" and stage == "creation" and #list > 0 then
        gateway:Stage(player, "selection")
        return {ok = true}
    end
    if stage ~= "selection" then return {ok = false, error = "selection_not_pending"} end
    if action == "new" then
        if #list >= gateway.profiles.Limit then return {ok = false, error = "character_slots_full"} end
        gateway:Stage(player, "creation")
        return {ok = true}
    end
    if action ~= "delete" or type(id) ~= "string" or id ~= selectedId then
        return {ok = false, error = "character_unavailable"}
    end
    if os.clock() < (gateway.nextRequest[player] or 0) then return {ok = false, error = "rate_limited"} end
    gateway.nextRequest[player] = os.clock() + 1.5
    if not gateway.profiles.Delete(player, id) then return {ok = false, error = "character_save_failed"} end
    RosterGateway.Publish(gateway, player)
    gateway.nextRequest[player] = nil
    if not gateway.profiles.Get(player) then gateway:Stage(player, "creation") end
    return {ok = true}
end
function RosterGateway.Bind(gateway: any, remotes: Folder)
    local remote = remotes:FindFirstChild("CharacterCreationRoster") or Instance.new("RemoteFunction")
    assert(remote:IsA("RemoteFunction"), "CharacterCreationRoster must be RemoteFunction")
    remote.Name = "CharacterCreationRoster"
    remote.Parent = remotes
    remote.OnServerInvoke = function(player: Player, action: any, id: any)
        return gateway:Request(player, function() return RosterGateway.Change(gateway, player, action, id) end)
    end
end
return table.freeze(RosterGateway)

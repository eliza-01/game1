-- Published TestPlace debug controls. Checkbox is not authorization.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Shared = script.Parent.Parent
local Options = require(Shared:WaitForChild("GameOptions"))

local Access = {}
local AUTH_ATTRIBUTE = "Game1PublishedDebugAuthorized"
local warnedAuthorization = false

function Access.ServerEnabled(): boolean
    return RunService:IsStudio()
        or Options.ShowPublishedDebugControls("desktop")
        or Options.ShowPublishedDebugControls("mobile")
end

function Access.ServerAllowed(player: Player): boolean
    return RunService:IsStudio() or (Access.ServerEnabled() and player:GetAttribute(AUTH_ATTRIBUTE) == true)
end

function Access.ClientAllowed(): boolean
    if RunService:IsStudio() then return true end
    local device = if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
        then "mobile" else "desktop"
    if not Options.ShowPublishedDebugControls(device) then return false end
    local player = Players.LocalPlayer
    if not player then return false end
    -- The attribute is written by the server after joining, never by the client.
    local deadline = os.clock() + 12
    while player:GetAttribute(AUTH_ATTRIBUTE) == nil and os.clock() < deadline do
        task.wait(0.1)
    end
    local allowed = player:GetAttribute(AUTH_ATTRIBUTE) == true
    if not allowed and not warnedAuthorization then
        warnedAuthorization = true
        warn("[game1][debug] Published controls enabled, but Roblox creator authorization denied. "
            .. "Group developer requires rank >= 200; check the owner/group role.")
    end
    return allowed
end

return table.freeze(Access)

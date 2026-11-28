-- One global published debug switch; server authorizes every admitted player.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Shared = script.Parent.Parent
local Options = require(Shared:WaitForChild("GameOptions"))

local Access = {}
local function compiledRuntime(): boolean
    return game:GetService("ReplicatedStorage"):FindFirstChild("Game1LocationRuntimeManifest") ~= nil
end
local AUTH_ATTRIBUTE = "Game1PublishedDebugAuthorized"
local warnedAuthorization = false

function Access.GameplayTestEnabled(): boolean
    return RunService:IsStudio() and (not compiledRuntime() or Options.StartInGameplayHub())
end

function Access.ServerEnabled(): boolean
    return RunService:IsStudio()
        or Options.ShowPublishedDebugControls()
end

function Access.ServerAllowed(player: Player): boolean
    return RunService:IsStudio() or (Access.ServerEnabled() and player:GetAttribute(AUTH_ATTRIBUTE) == true)
end

function Access.ClientAllowed(): boolean
    if RunService:IsStudio() then return true end
    if not Options.ShowPublishedDebugControls() then return false end
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
        warn("[game1][debug] Published debug authorization not received from server.")
    end
    return allowed
end

return table.freeze(Access)

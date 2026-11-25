--!strict
-- Server-owned replication focus for a distant presentation scene.
-- Roblox streams detailed terrain around the actual player character by default;
-- while pending selection we keep only the creation area additionally loaded.
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SelectionScene = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("character"):WaitForChild("CharacterSelectionScene"))

local Service = {}
local started = false

function Service.Start(settings: any)
    if started or settings.enabled ~= true then return end
    started = true
    local anchors = SelectionScene.Resolve()
    local function declare(player: Player)
        player:SetAttribute("Game1CharacterSelectionScene", anchors ~= nil)
    end
    Players.PlayerAdded:Connect(declare)
    for _, player in Players:GetPlayers() do declare(player) end
    if not Workspace.StreamingEnabled then return end
    local male = (settings.spawnPoints or {}).male
    local female = (settings.spawnPoints or {}).female
    if not male or not female then return end
    local a = male.position
    local b = female.position
    if type(a) ~= "table" or type(b) ~= "table" then return end
    local midpoint = Vector3.new((a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5, (a[3] + b[3]) * 0.5)
    local focus = Instance.new("Part")
    focus.Name = "Game1CreationStreamingFocus"
    focus.Anchored = true
    focus.Size = Vector3.new(1, 1, 1)
    focus.Transparency = 1
    focus.CastShadow = false
    focus.CanCollide = false
    focus.CanTouch = false
    focus.CanQuery = false
    focus.CFrame = CFrame.new(midpoint)
    focus.Parent = Workspace
    local selectionFocus: Part? = nil
    if anchors then
        local marker = focus:Clone()
        marker.Name = "Game1SelectionStreamingFocus"
        marker.CFrame = CFrame.new(anchors.preview.Position)
        marker.Parent = Workspace
        selectionFocus = marker
    end
    local focused: {[Player]: boolean} = {}
    local selectedFocus: {[Player]: boolean} = {}
    local streamStages: {[Player]: string} = {}
    local streamTokens: {[Player]: number} = {}
    local subscriptions: {[Player]: {RBXScriptConnection}} = {}

    local function set(player: Player)
        local needed = player:GetAttribute("CharacterCreationPending") == true
        local selection = selectionFocus
        local selectionNeeded = needed and player:GetAttribute("CharacterCreationStatus") == "selection"
        if selection and selectionNeeded ~= (selectedFocus[player] == true) then
            local ok, reason = pcall(function()
                if selectionNeeded then player:AddReplicationFocus(selection)
                else player:RemoveReplicationFocus(selection) end
            end)
            if ok then selectedFocus[player] = if selectionNeeded then true else nil
            else warn("[game1][character-creation] selection focus: " .. tostring(reason)) end
        end
        if needed and not focused[player] then
            local ok, reason = pcall(function() player:AddReplicationFocus(focus) end)
            if not ok then
                warn("[game1][character-creation] terrain focus unavailable: " .. tostring(reason))
                return
            end
            focused[player] = true
        elseif not needed and focused[player] then
            focused[player] = nil
            local ok, reason = pcall(function() player:RemoveReplicationFocus(focus) end)
            if not ok then warn("[game1][character-creation] focus cleanup: " .. tostring(reason)) end
        end
        local stage = if needed then tostring(player:GetAttribute("CharacterCreationStatus") or "loading") else "world"
        if streamStages[player] == stage then return end
        streamStages[player] = stage
        local token = (streamTokens[player] or 0) + 1
        streamTokens[player] = token
        player:SetAttribute("Game1CharacterSceneStreamReady", nil)
        if stage == "creation" or stage == "selection" then
            task.spawn(function()
                local success, message = pcall(function()
                    if stage == "selection" and selection then
                        player:RequestStreamAroundAsync(selection.Position, 6)
                    else
                        player:RequestStreamAroundAsync(midpoint, 6)
                    end
                end)
                if streamTokens[player] ~= token or not player.Parent then return end
                if success then player:SetAttribute("Game1CharacterSceneStreamReady", stage)
                else warn("[game1][character-creation] scene streaming: " .. tostring(message)) end
            end)
        end
    end
    local function join(player: Player)
        if subscriptions[player] then return end
        subscriptions[player] = {
            player:GetAttributeChangedSignal("CharacterCreationPending"):Connect(function() set(player) end),
            player:GetAttributeChangedSignal("CharacterCreationStatus"):Connect(function() set(player) end),
        }
        set(player)
    end
    Players.PlayerAdded:Connect(join)
    Players.PlayerRemoving:Connect(function(player)
        streamStages[player] = nil
        streamTokens[player] = nil
        if subscriptions[player] then
            for _, connection in subscriptions[player] do connection:Disconnect() end
            subscriptions[player] = nil
        end
        if selectedFocus[player] and selectionFocus then
            selectedFocus[player] = nil
            pcall(function() player:RemoveReplicationFocus(selectionFocus) end)
        end
        if focused[player] then
            focused[player] = nil
            pcall(function() player:RemoveReplicationFocus(focus) end)
        end
    end)
    for _, player in ipairs(Players:GetPlayers()) do join(player) end
end
return Service

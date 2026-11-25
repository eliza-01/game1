--!strict
-- One visual set per house. The authoritative lock state remains HousePadlockService.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Contract = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world"):WaitForChild("HouseSocketContract"))
local Mount = require(script.Parent:WaitForChild("HouseSocketAssetMount"))
local Visuals = {}
-- The published Padlock 02 mounts by its authored pivot.
local SLUG = "padlock_02"
type State = {attached: boolean, folder: Folder?}
local states: {[Model]: State} = {}

function Visuals.Clear(house: Model)
    local state = states[house]
    states[house] = nil
    if state and state.folder then state.folder:Destroy() end
end

function Visuals.SetAttached(house: Model, sockets: {[string]: Attachment}, attached: boolean)
    local previous = states[house]
    if previous and previous.attached == attached then return end
    Visuals.Clear(house)
    if not Contract.HasPadlock(sockets) then return end
    local state: State = {attached = attached, folder = nil}
    states[house] = state
    house:SetAttribute("Game1PadlockVisualStatus", if attached then "loading" else "detached")
    if not attached then return end
    task.defer(function()
        for attempt = 1, 3 do
            if states[house] ~= state then return end
            local folder = Instance.new("Folder")
            folder.Name = "Game1PadlockVisuals"
            local expected, mounted = 0, 0
            for _, name in Contract.PadlockSockets do
                local socket = sockets[name]
                if not socket then continue end
                expected += 1
                local ok, model = pcall(Mount.CloneOnPivot, SLUG, socket)
                if ok and model then
                    model.Name = name
                    model.Parent = folder
                    mounted += 1
                elseif not ok then
                    warn("[game1][padlock] mount failed: " .. tostring(model))
                end
                if states[house] ~= state then folder:Destroy(); return end
            end
            if expected > 0 and mounted == expected and house.Parent then
                state.folder = folder
                folder.Parent = house
                house:SetAttribute("Game1PadlockVisualStatus", "ready:" .. tostring(mounted))
                return
            end
            folder:Destroy()
            if attempt < 3 then task.wait(attempt * 2) end
        end
        if states[house] ~= state then return end
        house:SetAttribute("Game1PadlockVisualStatus", "asset_unavailable")
        warn("[game1][padlock] published visual unavailable for " .. house:GetFullName())
    end)
end
return table.freeze(Visuals)

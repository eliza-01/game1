--!strict
-- Semantic tinting for rigid compound hair. Reusable by startup assembly and
-- future in-game customization; no geometry/attachment knowledge lives here.
local HairColorBinder = {}

local CharacterColorBinder = require(script.Parent:WaitForChild("CharacterColorBinder"))

function HairColorBinder.Apply(hairModel: Model, colors: {[string]: string})
    if not colors then return end
    local channels: {[string]: MeshPart} = {}
    for _, item in hairModel:GetDescendants() do
        if item:IsA("MeshPart") then
            local channel = item:GetAttribute("HairColorChannel")
            if typeof(channel) == "string" then
                assert(channels[channel] == nil, "duplicate hair color channel " .. channel)
                channels[channel] = item
            end
        end
    end
    for channel, hex in colors do
        local mesh = assert(channels[channel], "unknown hair color channel: " .. tostring(channel))
        CharacterColorBinder.Apply(mesh, hex)
    end
end

return table.freeze(HairColorBinder)

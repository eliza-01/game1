--!strict
-- Server pre-stages explicitly whitelisted, published SINGLE-MeshPart Location
-- assets for local cosmetic VFX. No Workspace placement or distance LOD change.
-- Reuses LocationLodTemplateService's guarded immutable Model loader.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Options = require(Shared:WaitForChild("GameOptionsRegistry"))
local Registry = require(Shared:WaitForChild("world"):WaitForChild("LocationAssetRegistry"))
local Service = {}
Service.FolderName = "Game1ResidentEffectTemplates"
local started = false

function Service.Start(loadPrototype: (number, string) -> MeshPart?)
    if started then return end
    started = true
    local folder = Instance.new("Folder")
    folder.Name = Service.FolderName
    folder:SetAttribute("Ready", false)
    folder.Parent = ReplicatedStorage
    task.spawn(function()
        local total, ready = 0, 0
        for _, slug in ipairs((Options.flora or {}).residentAssets or {}) do
            total += 1
            local entry = Registry.assets[slug]
            if not entry or entry.status ~= "PUBLISHED" then
                warn("[game1][resident] not published: " .. tostring(slug))
                continue
            end
            local id = tonumber(entry.modelAssetId)
            if not id then
                warn("[game1][resident] missing Model ID: " .. slug)
                continue
            end
            local prototype = loadPrototype(id, slug .. "__RESIDENT")
            if prototype and prototype:IsA("MeshPart") then
                prototype.Name = slug
                prototype.Parent = folder
                ready += 1
            else
                if prototype then prototype:Destroy() end
                warn("[game1][resident] expected exactly one published visual MeshPart: " .. slug)
            end
        end
        folder:SetAttribute("Ready", true)
        folder:SetAttribute("Loaded", ready)
        folder:SetAttribute("Expected", total)
        if ready ~= total then
            warn(("[game1][resident] only %d/%d resident effect templates ready"):format(ready, total))
        end
    end)
end
return table.freeze(Service)

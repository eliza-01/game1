--!strict
-- Identifies placed houses by authoring identity, not Workspace folder names.
-- Studio may also preview an authored HouseRig before its slug is assigned.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Contract = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world"):WaitForChild("HouseSocketContract"))

local Discovery = {}

function Discovery.IsHouse(instance: Instance): boolean
    if not instance:IsA("Model") or not instance:IsDescendantOf(Workspace) then
        return false
    end
    local isStudio = RunService:IsStudio()
    local isTemplate = instance:GetAttribute("Game1RealEstateTemplate") == true
    -- Production never registers template models. An authored copy in Studio
    -- may still carry that tag; actual socket bones qualify it as a preview.
    if isTemplate and not isStudio then return false end
    local slug = instance:GetAttribute("Game1RealEstateSlug")
    if not isTemplate and typeof(slug) == "string" and slug ~= "" then return true end
    if not RunService:IsStudio() then return false end
    -- Deliberate Studio-only authoring fallback: a real house rig with an
    -- authored, known socket. Never guess a socket position or trust a name.
    local rig = instance:FindFirstChild("HouseRig")
    if not rig or not rig:IsA("Model") then return false end
    for _, descendant in rig:GetDescendants() do
        if descendant:IsA("Attachment") and Contract.Get(descendant.Name) then
            return true
        end
    end
    return false
end

function Discovery.IsPotentialHouseRoot(instance: Instance): boolean
    return instance:IsA("Model") and (
        instance:GetAttribute("Game1RealEstateSlug") ~= nil
        or instance:FindFirstChild("HouseRig") ~= nil
        or instance:FindFirstChild("DoorAssembly") ~= nil
    )
end

function Discovery.OwnerOf(instance: Instance): Model?
    local cursor: Instance? = instance
    while cursor and cursor ~= Workspace do
        if Discovery.IsHouse(cursor) then return cursor :: Model end
        cursor = cursor.Parent
    end
    return nil
end

return table.freeze(Discovery)

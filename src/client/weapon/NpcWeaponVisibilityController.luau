-- Event-driven local rendering of NPC equipment presentation state.
-- WeaponAttachmentController owns socket following independently of this module.
-- No animation track, death state or render-frame code can equip/unequip a weapon here.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Contract = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("weapon"):WaitForChild("WeaponPresentationContract"))

local NpcWeaponVisibilityController = {}
local started = false
local boundFolder: Folder? = nil
local folderConnections = {}
local actorStates: {[Model]: any} = {}
local EQUIPPED_NAMES = { EquippedWeaponRight = true, EquippedWeaponLeft = true }

local function setPartHidden(weaponState: any, part: BasePart, hidden: boolean)
    local originals = weaponState.originals
    if hidden then
        if originals[part] == nil then
            originals[part] = part.LocalTransparencyModifier
        end
        part.LocalTransparencyModifier = 1
    elseif originals[part] ~= nil then
        part.LocalTransparencyModifier = originals[part]
        originals[part] = nil
    end
end

local function applyWeapon(weaponState: any, hidden: boolean)
    for _, node in ipairs(weaponState.model:GetDescendants()) do
        if node:IsA("BasePart") then
            setPartHidden(weaponState, node, hidden)
        end
    end
end

local function unbindWeapon(actorState: any, weapon: Model)
    local weaponState = actorState.weapons[weapon]
    if not weaponState then
        return
    end
    actorState.weapons[weapon] = nil
    weaponState.descendantAdded:Disconnect()
    applyWeapon(weaponState, false)
end

local function bindWeapon(actorState: any, weapon: Model)
    if actorState.weapons[weapon] or not EQUIPPED_NAMES[weapon.Name]
        or weapon:GetAttribute("Game1WeaponAttachment") ~= true then
        return
    end
    local weaponState = {
        model = weapon,
        originals = {},
    }
    actorState.weapons[weapon] = weaponState
    weaponState.descendantAdded = weapon.DescendantAdded:Connect(function(node)
        if node:IsA("BasePart") and actorState.hidden then
            setPartHidden(weaponState, node, true)
        end
    end)
    if actorState.hidden then
        applyWeapon(weaponState, true)
    end
end

local function syncActor(actorState: any)
    local hidden = actorState.actor:GetAttribute(Contract.HiddenAttribute) == true
    if actorState.hidden == hidden then
        return
    end
    actorState.hidden = hidden
    for _, weaponState in pairs(actorState.weapons) do
        applyWeapon(weaponState, hidden)
    end
end

local function unbindActor(actor: Model)
    local actorState = actorStates[actor]
    if not actorState then
        return
    end
    actorStates[actor] = nil
    for _, connection in ipairs(actorState.connections) do
        connection:Disconnect()
    end
    local weapons = {}
    for weapon in pairs(actorState.weapons) do
        table.insert(weapons, weapon)
    end
    for _, weapon in ipairs(weapons) do
        unbindWeapon(actorState, weapon)
    end
end

local function bindActor(actor: Instance)
    if not actor:IsA("Model") or actorStates[actor] then
        return
    end
    local state = {
        actor = actor,
        weapons = {},
        hidden = actor:GetAttribute(Contract.HiddenAttribute) == true,
        connections = {},
    }
    actorStates[actor] = state
    table.insert(state.connections, actor:GetAttributeChangedSignal(Contract.HiddenAttribute):Connect(function()
        syncActor(state)
    end))
    table.insert(state.connections, actor.ChildAdded:Connect(function(child)
        if child:IsA("Model") then
            bindWeapon(state, child)
        end
    end))
    table.insert(state.connections, actor.ChildRemoved:Connect(function(child)
        if child:IsA("Model") then
            unbindWeapon(state, child)
        end
    end))
    for _, child in ipairs(actor:GetChildren()) do
        if child:IsA("Model") then
            bindWeapon(state, child)
        end
    end
end

local function bindFolder(folder: Folder)
    if boundFolder == folder then
        return
    end
    for _, connection in ipairs(folderConnections) do
        connection:Disconnect()
    end
    table.clear(folderConnections)
    local actors = {}
    for actor in pairs(actorStates) do
        table.insert(actors, actor)
    end
    for _, actor in ipairs(actors) do
        unbindActor(actor)
    end
    boundFolder = folder
    table.insert(folderConnections, folder.ChildAdded:Connect(bindActor))
    table.insert(folderConnections, folder.ChildRemoved:Connect(function(actor)
        if actor:IsA("Model") then
            unbindActor(actor)
        end
    end))
    for _, actor in ipairs(folder:GetChildren()) do
        bindActor(actor)
    end
end

function NpcWeaponVisibilityController.Start()
    if started then
        return
    end
    started = true
    local current = workspace:FindFirstChild("NPCs")
    if current and current:IsA("Folder") then
        bindFolder(current)
    end
    workspace.ChildAdded:Connect(function(child)
        if child.Name == "NPCs" and child:IsA("Folder") then
            bindFolder(child)
        end
    end)
    workspace.ChildRemoved:Connect(function(child)
        if child == boundFolder then
            for _, connection in ipairs(folderConnections) do
                connection:Disconnect()
            end
            table.clear(folderConnections)
            local actors = {}
            for actor in pairs(actorStates) do
                table.insert(actors, actor)
            end
            for _, actor in ipairs(actors) do
                unbindActor(actor)
            end
            boundFolder = nil
        end
    end)
end

return table.freeze(NpcWeaponVisibilityController)

local Players = game:GetService("Players")
local PlayerStatusController = {}
local gui: ScreenGui? = nil
local label: TextLabel? = nil
local connections = {}
local function clearConnections() for _, c in ipairs(connections) do c:Disconnect() end table.clear(connections) end
local function render(character)
    if not label then return end
    if not character then label.Text = "NO CHARACTER" return end
    label.Text = ("LV %d   HP %d/%d   DMG %d   DEF %d   ASPD %d   RUN %d   %s"):format(
        character:GetAttribute("Level") or 1, character:GetAttribute("HP") or 0,
        character:GetAttribute("MaxHP") or 0, character:GetAttribute("Damage") or 0,
        character:GetAttribute("Defense") or 0, character:GetAttribute("AttackSpeed") or 100,
        character:GetAttribute("RunSpeed") or 50, tostring(character:GetAttribute("EquippedWeaponSlug") or "hands"))
end
local function bind(character)
    clearConnections(); render(character)
    if not character then return end
    for _, name in ipairs({"Level","HP","MaxHP","Damage","Defense","AttackSpeed","RunSpeed","EquippedWeaponSlug"}) do
        table.insert(connections, character:GetAttributeChangedSignal(name):Connect(function() render(character) end))
    end
end
function PlayerStatusController.Start()
    local player = Players.LocalPlayer
    gui = Instance.new("ScreenGui"); gui.Name="game1Status"; gui.ResetOnSpawn=false; gui.Parent=player:WaitForChild("PlayerGui")
    label=Instance.new("TextLabel"); label.Size=UDim2.fromOffset(720,36); label.Position=UDim2.fromOffset(18,18); label.BackgroundTransparency=0.3; label.TextScaled=true; label.TextXAlignment=Enum.TextXAlignment.Left; label.Parent=gui
    player.CharacterAdded:Connect(bind); bind(player.Character)
end
return PlayerStatusController

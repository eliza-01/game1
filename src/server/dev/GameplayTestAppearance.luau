--!strict
local Appearance = {}
local armorSlots = {upper=true, lower=true, boots=true, gloves=true}
function Appearance.Tint(root: Instance, color: Color3, clothingOnly: boolean?)
    for _, item in ipairs(root:GetDescendants()) do
        if item:IsA("MeshPart") and (not clothingOnly or armorSlots[tostring(item:GetAttribute("CharacterPartSlot"))]) then
            for _, child in ipairs(item:GetChildren()) do
                if child:IsA("SurfaceAppearance") or child:IsA("Decal") or child:IsA("Texture") then child:Destroy() end
            end
            item.TextureID = ""
            item.Color = color
            item.Material = Enum.Material.SmoothPlastic
        end
    end
end
function Appearance.Label(model: Model, text: string, color: Color3, adornee: BasePart?)
    local root = adornee or model:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then return end
    local gui = Instance.new("BillboardGui")
    gui.Name = "GameplayTestLabel"
    gui.Adornee = root
    gui.Size = UDim2.fromOffset(230, 48)
    gui.StudsOffsetWorldSpace = Vector3.new(0, root.Size.Y / 2 + 2.5, 0)
    gui.MaxDistance = 95
    gui.AlwaysOnTop = true
    gui.Parent = root
    local label = Instance.new("TextLabel")
    label.Size = UDim2.fromScale(1, 1)
    label.BackgroundTransparency = 1
    label.Font = Enum.Font.GothamBold
    label.TextSize = 15
    label.TextColor3 = color
    label.TextStrokeTransparency = 0.2
    label.Text = text
    label.Parent = gui
    if string.sub(tostring(model:GetAttribute("MonsterBalanceId") or ""),1,8)=="skilled_" then
        gui.Size = UDim2.fromOffset(270,64)
        label.Size = UDim2.new(1,0,0,44)
        local status = Instance.new("TextLabel")
        status.BackgroundTransparency = 1; status.Position = UDim2.fromOffset(0,44); status.Size = UDim2.new(1,0,0,20)
        status.TextColor3 = Color3.fromRGB(232,185,255); status.Font = Enum.Font.GothamBold; status.TextSize = 14; status.TextStrokeTransparency = .2; status.Parent = gui
        local function update() status.Text = tostring(model:GetAttribute("ActiveSkillEffects") or "") end
        model:GetAttributeChangedSignal("ActiveSkillEffects"):Connect(update)
        update()
    end
end
return table.freeze(Appearance)

--!strict
-- Studio-only world panels. No client supplied target, gear ID or teleport frame.
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance=require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Panels={}
local function panel(parent: Instance, name: string, frame: CFrame, color: Color3, label: string, action: string, callback: (Player, BasePart)->())
    local part=Instance.new("Part")
    part.Name=name; part.Size=Vector3.new(7,5,1); part.CFrame=frame
    part.Anchored=true; part.CanCollide=false; part.CanTouch=false; part.CanQuery=false
    part.Color=color; part.Material=Enum.Material.SmoothPlastic; part.Parent=parent
    local gui=Instance.new("SurfaceGui"); gui.Face=Enum.NormalId.Front; gui.CanvasSize=Vector2.new(420,300); gui.Parent=part
    local text=Instance.new("TextLabel"); text.Size=UDim2.fromScale(1,1); text.BackgroundTransparency=1
    text.Font=Enum.Font.GothamBold; text.TextScaled=true; text.TextWrapped=true; text.TextColor3=Color3.new(1,1,1); text.Text=label; text.Parent=gui
    local prompt=Instance.new("ProximityPrompt"); prompt.ActionText=action; prompt.ObjectText=label:gsub("\n"," · ")
    prompt.MaxActivationDistance=10; prompt.RequiresLineOfSight=false; prompt.HoldDuration=0; prompt.Parent=part
    prompt.Triggered:Connect(function(player) callback(player,part) end)
end
function Panels.Build(parent: Instance, layout: any, onVisit: (Player,BasePart,number?)->(), onGear: (Player,BasePart,number)->())
    local folder=Instance.new("Folder"); folder.Name="ZonePanels"; folder.Parent=parent
    local levels={"Weak","Medium","Strong"}
    for index, zone in pairs(layout.boxes) do
        local x= -64+((index-1)%4)*42
        local z= 30+math.floor((index-1)/4)*20
        local row=layout.hub*CFrame.new(x,2,z)
        panel(folder,"Teleport_"..index,row,zone.color,zone.name.."\nLVL "..zone.low.."–"..zone.high,"Teleport",function(player,part) onVisit(player,part,index) end)
        for i, level in ipairs(zone.gear) do
            panel(folder,"Gear_"..index.."_"..i,row*CFrame.new(i*8,0,0),Color3.fromRGB(57+15*i,75+10*i,94),levels[i].." · "..Balance.Grade.ForLevel(level).."\nLVL "..level.." · +0","Equip",function(player,part) onGear(player,part,level) end)
        end
        local returnFrame=zone.entry*CFrame.new(-12,2,3)
        panel(folder,"Return_"..index,returnFrame,zone.color,"HUB","Return",function(player,part) onVisit(player,part,nil) end)
    end
end
return table.freeze(Panels)

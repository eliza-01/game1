--!strict
-- A single strip in the existing HP ScreenGui. Receipts report resolved stat
-- gains; the server publishes expiry and live gains after recomputing stats.
local Players=game:GetService("Players")
local RunService=game:GetService("RunService")
local TweenService=game:GetService("TweenService")
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Buffs=require(Shared:WaitForChild("combat"):WaitForChild("BuffDefinitions"))
local Visuals=require(script.Parent:WaitForChild("BuffCastVisuals"))
local Hud={}
local icon=require(script.Parent:WaitForChild("BuffIconView")).Create
local function label(parent: Instance,size: number): TextLabel
    local text=Instance.new("TextLabel"); text.BackgroundTransparency=1; text.Font=Enum.Font.GothamBold; text.TextSize=size; text.TextColor3=Color3.new(1,1,1); text.TextStrokeTransparency=.25; text.Parent=parent; return text
end
function Hud.Start(gui: ScreenGui,plate: Frame)
    -- Display-only layers: UiInputGuard must ignore these and their descendants,
    -- including the fullscreen receipt canvas even when no buffs are active.
    local strip=Instance.new("Frame"); strip.Name="BuffStrip"; strip.BackgroundTransparency=1; strip.Size=UDim2.fromOffset(132,42)
    strip.Active=false; strip:SetAttribute("WorldInputPassthrough", true); strip.Parent=gui
    local receipts=Instance.new("Frame"); receipts.Name="BuffReceipts"; receipts.BackgroundTransparency=1; receipts.Size=UDim2.fromScale(1,1)
    receipts.Active=false; receipts:SetAttribute("WorldInputPassthrough", true); receipts.Parent=gui
    local player=Players.LocalPlayer
    local watched: Model?=nil; local slots: {[string]: any}={}; local elapsed=0
    local function reset()
        strip:ClearAllChildren(); receipts:ClearAllChildren(); table.clear(slots)
    end
    local function receive(character: Model,row: any,slot: any,ordinal: number)
        Visuals.Play(character,row.color)
        local toast=icon(receipts,row,48); toast.ZIndex=5
        toast.Position=UDim2.new(.5,-100,.34,math.min(ordinal-1,3)*52)
        local text=label(toast,17); text.Position=UDim2.fromOffset(58,0); text.Size=UDim2.fromOffset(220,48); text.TextXAlignment=Enum.TextXAlignment.Left; text.TextColor3=row.color; text.ZIndex=6
        local gain=tonumber(character:GetAttribute("BuffGain_"..row.effect)) or 0
        text.Text=string.format("%s  +%g %s",row.name,math.round(gain*100)/100,row.unit)
        slot.toast=toast
        task.delay(1.1,function()
            if slots[row.effect]~=slot or not toast.Parent then return end
            local fade=TweenService:Create(text,TweenInfo.new(.18),{TextTransparency=1,TextStrokeTransparency=1}); fade:Play()
            fade.Completed:Wait()
            if slots[row.effect]~=slot or not toast.Parent then return end
            text:Destroy()
            local destination=slot.icon.AbsolutePosition-receipts.AbsolutePosition
            local flight=TweenService:Create(toast,TweenInfo.new(.4,Enum.EasingStyle.Quad,Enum.EasingDirection.InOut),{Position=UDim2.fromOffset(destination.X,destination.Y),Size=slot.icon.Size})
            flight:Play(); flight.Completed:Wait()
            if slots[row.effect]==slot and slot.icon.Parent then slot.icon.Visible=true; slot.timer.Visible=true; slot.toast=nil end
            toast:Destroy()
        end)
    end
    RunService.RenderStepped:Connect(function(dt)
        elapsed+=dt; if elapsed<.08 then return end; elapsed=0
        local character=player.Character
        if character~=watched then reset(); watched=character end
        if not character or character:GetAttribute("LifeState")~="Alive" then if next(slots) then reset() end; return end
        local left=plate.AbsolutePosition.X+plate.AbsoluteSize.X+8
        -- Keep right-of-HP on desktop; use the leftward strip below the bar
        -- only when a narrow screen cannot fit four readable icons.
        local width=receipts.AbsoluteSize.X
        local top=plate.AbsolutePosition.Y
        if left+132>width then left=math.max(4,width-136); top=top+plate.AbsoluteSize.Y+43 end
        strip.Position=UDim2.fromOffset(left-receipts.AbsolutePosition.X,top-receipts.AbsolutePosition.Y)
        local now=workspace:GetServerTimeNow(); local index=0
        for _,row in ipairs(Buffs.Rows) do
            local untilTime=tonumber(character:GetAttribute("BuffUntil_"..row.effect)) or 0
            local slot=slots[row.effect]
            if untilTime<=now then
                if slot then if slot.toast then slot.toast:Destroy() end; slot.icon:Destroy(); slot.timer:Destroy(); slots[row.effect]=nil end
            else
                index+=1
                if not slot then
                    local tile=icon(strip,row,28); tile.Visible=false
                    local timer=label(strip,10); timer.Size=UDim2.fromOffset(28,12); timer.Visible=false
                    slot={icon=tile,timer=timer}; slots[row.effect]=slot
                    receive(character,row,slot,index)
                end
                slot.icon.Position=UDim2.fromOffset((index-1)*33,0)
                slot.timer.Position=UDim2.fromOffset((index-1)*33,29)
                local remaining=math.ceil(untilTime-now)
                slot.timer.Text=string.format("%d:%02d",math.floor(remaining/60),remaining%60)
            end
        end
    end)
end
return table.freeze(Hud)

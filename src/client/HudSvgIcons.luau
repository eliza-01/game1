--!strict
-- Actual rasterized SVG artwork. Shared per client, allocated on first use only.
local AssetService = game:GetService("AssetService")
local Data = require(script.Parent:WaitForChild("world"):WaitForChild("HouseInteractionIconData"))
local MobileData = require(script.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileActionIconData"))
local Icons = {}
-- Optional published PNG IDs (when Mesh/Image APIs are disabled for the Experience).
local published: {[string]: string} = {} -- e.g. LockClosed = "rbxassetid://123"
local cache: {[string]: any} = {}
local fallback = {LockClosed = "🔒", LockOpen = "🔓", DoorClosed = "🚪", DoorOpen = "↪", Attack = "⚔", Jump = "↑", Aim = "⊙"}
local function imageFor(state: string): any?
    if cache[state] ~= nil then return cache[state] or nil end
    local encoded = (Data :: any)[state] or (MobileData :: any)[state]
    if not encoded then return nil end
    local image: EditableImage? = nil
    local ok, result = pcall(function()
        image = AssetService:CreateEditableImage({Size = Vector2.new(48, 48)})
        if not image then error("EditableImage budget unavailable") end
        local pixels = buffer.create(48 * 48 * 4)
        local offset = 0
        for i = 1, #encoded, 12 do
            local count = assert(tonumber(encoded:sub(i, i+3), 16))
            local r = assert(tonumber(encoded:sub(i+4, i+5), 16))
            local g = assert(tonumber(encoded:sub(i+6, i+7), 16))
            local b = assert(tonumber(encoded:sub(i+8, i+9), 16))
            local a = assert(tonumber(encoded:sub(i+10, i+11), 16))
            local rgba = r + g*256 + b*65536 + a*16777216
            for _ = 1, count do
                buffer.writeu32(pixels, offset, rgba)
                offset += 4
            end
        end
        assert(offset == buffer.len(pixels))
        local editable = image :: EditableImage
        editable:WritePixelsBuffer(Vector2.zero, Vector2.new(48, 48), pixels)
        return Content.fromObject(editable)
    end)
    if not ok then
        if image then image:Destroy() end
        warn("[game1][hud-icons] SVG image unavailable: " .. tostring(result))
    end
    cache[state] = if ok then {content = result, image = image} else false
    return cache[state] or nil
end
function Icons.Apply(button: TextButton, state: string)
    button.Text = ""
    local id = published[state]
    local art = if id then nil else imageFor(state)
    if id or art then
        local icon = Instance.new("ImageLabel")
        icon.Name = "InteractionStateIcon"
        icon.BackgroundTransparency = 1
        icon.Active = false
        icon.ZIndex = button.ZIndex + 1
        icon.AnchorPoint = Vector2.new(0.5, 0.5)
        icon.Position = UDim2.fromScale(0.5, 0.5)
        icon.Size = UDim2.fromScale(0.88, 0.88)
        icon.ScaleType = Enum.ScaleType.Fit
        if id then icon.Image = id else icon.ImageContent = art.content end
        icon.Parent = button
    else
        -- No words and no fake geometry when the platform denies image creation.
        button.Text = (fallback :: any)[state] or ""
        button.TextSize = 26
        button.TextColor3 = Color3.fromRGB(244,246,249)
    end
end
return table.freeze(Icons)

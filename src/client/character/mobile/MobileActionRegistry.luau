--!strict
-- The single touch router receives action surfaces from independent HUD views.
-- Non-touch activation and pre-character UI keep the ordinary Activated path.
local Registry = {}
local listener: ((InputObject, string, (() -> ())?) -> boolean)? = nil
function Registry.SetListener(callback: (InputObject, string, (() -> ())?) -> boolean)
    listener = callback
end
function Registry.Register(button: GuiButton, kind: string, onTap: (() -> ())?, fallbackTouch: boolean?)
    local claimed = setmetatable({}, {__mode = "k"})
    button.InputBegan:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.Touch and listener then
            claimed[input] = listener(input, kind, onTap) or nil
        end
    end)
    if onTap then
        button.Activated:Connect(function(input)
            if not input or input.UserInputType ~= Enum.UserInputType.Touch
                or (fallbackTouch and not claimed[input]) then onTap() end
        end)
    end
end
return table.freeze(Registry)

--!strict
-- Editor test stands are authoring references, not runtime preview actors.
-- Hide only marked stands inside the character-creation scene for this client;
-- preserve their original local appearance and restore it on exit.
local Stage = {}

type Hidden = {part: BasePart, transparency: number, shadow: boolean}

function Stage.Hide(scene: Instance?): {Hidden}
    local hidden: {Hidden} = {}
    if not scene then return hidden end
    for _, child in ipairs(scene:GetDescendants()) do
        if child:IsA("Model") and child:GetAttribute("Game1CharacterTestStand") == true then
            for _, part in ipairs(child:GetDescendants()) do
                if part:IsA("BasePart") then
                    table.insert(hidden, {part = part,
                        transparency = part.LocalTransparencyModifier, shadow = part.CastShadow})
                    part.LocalTransparencyModifier = 1
                    part.CastShadow = false
                end
            end
        end
    end
    return hidden
end

function Stage.Restore(hidden: {Hidden})
    for _, original in ipairs(hidden) do
        if original.part.Parent then
            original.part.LocalTransparencyModifier = original.transparency
            original.part.CastShadow = original.shadow
        end
    end
end

return Stage

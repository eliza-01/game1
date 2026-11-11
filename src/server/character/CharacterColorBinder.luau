--!strict
-- Shared solid-color/tint application for authorable character geometry.
-- Does not create or remove atlas assets; caller selects a semantic slot/channel.
local Binder = {}

function Binder.Parse(hex: string): Color3
    assert(typeof(hex) == "string" and hex:match("^#[0-9a-fA-F]+$") and #hex == 7,
        "character color must be #RRGGBB")
    return Color3.fromRGB(
        tonumber(hex:sub(2, 3), 16) :: number,
        tonumber(hex:sub(4, 5), 16) :: number,
        tonumber(hex:sub(6, 7), 16) :: number)
end

function Binder.Apply(mesh: MeshPart, hex: string)
    local tint = Binder.Parse(hex)
    local appearance = mesh:FindFirstChildOfClass("SurfaceAppearance")
    if appearance then
        appearance.Color = tint
    else
        mesh.Color = tint
    end
end

return table.freeze(Binder)

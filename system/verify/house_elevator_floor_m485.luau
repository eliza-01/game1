-- Standalone deterministic regression. Run with Luau CLI from game1 root:
-- luau system/verify/house_elevator_floor_m485.luau
local Policy = require("../../src/shared/world/HouseElevatorPolicy")
local two = {[1] = 0, [2] = 10}
local three = {[1] = -40, [2] = -30, [3] = -20}
local present = {[1] = true, [2] = true, [3] = true}
local function floor(y, heights, expected)
    assert(Policy.CurrentFloor(y, heights, 1) == expected, "unexpected floor at " .. y)
end
floor(1, two, 1)
floor(3, two, 1)
floor(11, two, 2)
floor(13, two, 2)
floor(7, two, nil)
floor(-39, three, 1)
floor(-27, three, 2)
floor(-19, three, 3)
floor(3, {[1] = 0, [2] = 2}, nil) -- overlapping bands must not guess
floor(0, {}, nil)
for current = 1, 3 do
    for _, route in Policy.Options(current, present) do
        assert(route.destination ~= current)
    end
end
assert(Policy.Resolve(1, "F", present) == nil)
assert(Policy.Resolve(2, "F", present).destination == 1)
assert(Policy.Resolve(3, "F", present).destination == 2)
assert(Policy.Resolve(2, "E", {[1] = true, [2] = true}).destination == 1)
print("M485 elevator floor policy: OK")

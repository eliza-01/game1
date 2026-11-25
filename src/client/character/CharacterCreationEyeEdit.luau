--!strict
-- The unlocked pair is a draft snapshot, never part of the saved appearance.
local Edit = {}
export type Pair = {l: string, r: string}
export type State = {locked: boolean, previous: Pair?}
function Edit.New(pair: Pair): State
    return {locked = pair.l == pair.r, previous = table.clone(pair)}
end
function Edit.Paint(pair: Pair, side: string, value: string, locked: boolean): Pair
    if locked then return {l = value, r = value} end
    if side == "l" then return {l = value, r = pair.r} end
    assert(side == "r", "invalid eye side")
    return {l = pair.l, r = value}
end
function Edit.Toggle(state: State, pair: Pair, side: string): Pair
    if state.locked then
        state.locked = false
        return table.clone(state.previous or pair)
    end
    state.previous = table.clone(pair)
    state.locked = true
    return Edit.Paint(pair, side, if side == "l" then pair.l else pair.r, true)
end
return table.freeze(Edit)

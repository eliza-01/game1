-- Device presentation policy only; published access is checked separately.
local Profile = {}
local desktop = table.freeze({slots = table.freeze({ TL = 0, CS = 1, HS = 2, CD = 3, HP = 4, UI = 5, GP = 6, AG = 7, LD = 8 }), count = 9})
local mobileStudio = table.freeze({slots = table.freeze({ GP = 0, UI = 1, HP = 2, CD = 3, LD = 4 }), count = 5})
local mobileRuntime = table.freeze({slots = table.freeze({ UI = 0, HP = 1, CD = 2, LD = 3 }), count = 4})
function Profile.Resolve(mobile, gameplayEnabled)
    if not mobile then return desktop end
    if gameplayEnabled then return mobileStudio end
    return mobileRuntime
end
return table.freeze(Profile)

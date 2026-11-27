-- Encounter-local progress, independent of navigation plan and damage timer.
-- Sample once per second. A repeated vertical pulse/slide inside the same
-- envelope is not new progress. No geometry queries or background tasks.
local Watchdog={}
local HORIZONTAL_PROGRESS=2
local VERTICAL_PROGRESS=.5
function Watchdog.Step(state,position,now,timeout)
    local w=state.stuckWatchdog
    if not w then
        w={anchor=position,minY=position.Y,maxY=position.Y,lastProgress=now,sampleAt=now,seconds=0}
        state.stuckWatchdog=w
    elseif now-w.sampleAt>=1 then
        w.sampleAt=now
        local dx,dz=position.X-w.anchor.X,position.Z-w.anchor.Z
        if dx*dx+dz*dz>=HORIZONTAL_PROGRESS^2 then
            w.anchor=position; w.minY=position.Y; w.maxY=position.Y; w.lastProgress=now
        elseif position.Y>=w.maxY+VERTICAL_PROGRESS then
            w.maxY=position.Y; w.lastProgress=now
        elseif position.Y<=w.minY-VERTICAL_PROGRESS then
            w.minY=position.Y; w.lastProgress=now
        end
        w.seconds=math.floor(now-w.lastProgress)
    end
    return w.seconds>=(timeout or 30),w.seconds
end
return table.freeze(Watchdog)

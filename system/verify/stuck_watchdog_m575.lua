table.freeze=function(t) return t end
local W=assert(loadfile(arg[1]))()
local function pos(x,y,z) return {X=x,Y=y,Z=z} end
local s={}
assert(not W.Step(s,pos(0,0,0),0,30))
for i=1,29 do assert(not W.Step(s,pos(0,0,0),i,30)) end
local expired,seconds=W.Step(s,pos(0,0,0),30,30)
assert(expired and seconds==30)
-- Identical repeated vertical pulses do not reset the timer indefinitely.
s={}; W.Step(s,pos(0,0,0),0,30)
for i=1,30 do assert(not W.Step(s,pos(0,i%2,0),i,30)) end
assert(W.Step(s,pos(0,1,0),31,30))
-- Real uphill and horizontal movement renew progress even on a long route.
s={}; W.Step(s,pos(0,0,0),0,30)
for i=1,100 do local e,n=W.Step(s,pos(i, i*.1,0),i,30);assert(not e and n<=1) end
-- Local jitter below the progress thresholds must not renew the timer.
s={}; W.Step(s,pos(0,0,0),0,5)
for i=1,4 do assert(not W.Step(s,pos(i%2*.4,0,0),i,5)) end
assert(W.Step(s,pos(0,0,0),5,5))
print('M575 watchdog: stationary, repeat pulses, movement, config and jitter passed')

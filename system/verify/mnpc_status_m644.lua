local View = dofile('src/client/dev/MnpcStatusView.luau')
local s = {counts={FULL=11,LOD1=9,UNLOADED=0,UNTRACKED=0},serverCounts={full=18,shell=2,loading=0,preparing=0,fault=0,unregistered=0},rows={}}
for i=1,20 do
    local shell = i>=19
    s.rows[i] = {name='actor_'..i,kind=i<=12 and 'NPC' or 'Monster',distance=i*10,actual=i<=11 and 'FULL' or 'LOD1',desired=i<=11 and 'FULL' or 'LOD1',reason='distance',server=shell and 'shell' or 'full',meshes=shell and 0 or 2,bones=shell and 0 or 75,animators=shell and 0 or 1,hitboxes=shell and 0 or 63,audit=i==19 and 'shell M0 B0 A0 H0' or nil}
end
local r = View.Build(s,true)
assert(#r.groups==2 and r.groups[1].name=='Monsters' and #r.groups[1].rows==8 and #r.groups[2].rows==12)
assert(r.groups[1].rows[1].title:find('actor_13',1,true) and r.groups[1].rows[8].title:find('actor_20',1,true))
local summary=table.concat(r.summary,'\n')
assert(summary:find('Observed: 20',1,true) and summary:find('Monsters 8',1,true) and summary:find('NPC 12',1,true))
assert(summary:find('FULL 11',1,true) and summary:find('LOD1 9',1,true))
assert(summary:find('36 meshes · 1350 bones · 18 animators',1,true))
assert(summary:find('Server hitboxes: 1134',1,true))
assert(summary:find('Shells released: 1/2',1,true))
assert(r.groups[1].rows[7].server:find('Released at transition',1,true))
assert(r.groups[1].rows[8].server:find('No audit',1,true))
s.rows[20].audit='shell M0 B2 A1 H0'
assert(View.Build(s,true).groups[1].rows[8].server:find('Check shell audit',1,true))
assert(View.Build(nil,false,'No controller').summary[2]=='No controller')
s.serverCounts.shell=0
assert(table.concat(View.Build(s,true).summary,'\n'):find('Shell release: not observed',1,true))
print('MNPC summary: 20 rows, grouped, totals and shell evidence verified')

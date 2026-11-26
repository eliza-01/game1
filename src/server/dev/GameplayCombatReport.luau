--!strict
-- Studio-only authoritative encounter counters. No client-supplied measurements.
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Movement = require(Shared:WaitForChild("character"):WaitForChild("CharacterMovementConfig"))
local Fallback = require(Shared:WaitForChild("combat"):WaitForChild("GameplayAttackFallback"))
local Report = {}
local current: any = nil -- one arena owner per server
local function number(model: Model, name: string): number
    return tonumber(model:GetAttribute(name)) or 0
end
local function round(v: number): number return math.round(v*1000)/1000 end
function Report.Begin(player: Player, character: Model, target: Model, stage: any)
    assert(RunService:IsStudio() and current == nil)
    current = {player=player, character=character, target=target, stage=stage, started=os.clock(),
        dealt=0, received=0, periodicReceived=0, hits=0, crits=0, headshots=0, incomingHits=0,
        incomingCrits=0, attacks=0, hitCycles=0, lastHitSerial=nil, firstHit=nil, debuffSeconds=0,
        centerRangeSeconds=nil, fallbackAttacks=0, effects={}, castCounts={}, clips={}, playerHP=number(character,"HP"), targetHP=number(target,"HP"),
        playerAS=number(character,"AttackSpeed"), playerATK=number(character,"Damage"), playerRunSpeed=number(character,"RunSpeed"),
        monsterAS=number(target,"AttackSpeed"), monsterATK=number(target,"Damage"), monsterRunSpeed=number(target,"RunSpeed")}
end
function Report.Attack(character: Model, _serial: number, clipId: string)
    local r=current
    if r and r.character==character then
        r.attacks+=1; r.clips[clipId]=(r.clips[clipId] or 0)+1
        if clipId==Fallback.ClipId then r.fallbackAttacks+=1 end
    end
end
function Report.Damage(attacker: Model?, target: Model, actual: number, critical: boolean, headshot: boolean, periodic: boolean)
    local r=current
    if not r then return end
    if attacker==r.character and target==r.target then
        r.dealt+=actual
        if not periodic then
            r.hits+=1; if critical then r.crits+=1 end; if headshot then r.headshots+=1 end
            local serial=number(r.character,"AttackSerial")
            if r.lastHitSerial~=serial then r.hitCycles+=1; r.lastHitSerial=serial end
        end
        if actual>0 and not r.firstHit then r.firstHit=os.clock()-r.started end
    elseif attacker==r.target and target==r.character then
        r.received+=actual
        if periodic then r.periodicReceived+=actual else r.incomingHits+=1; if critical then r.incomingCrits+=1 end end
    end
end
function Report.Cast(source: Model, skillId: string, applied: boolean?)
    local r=current
    if r and source==r.target then
        local entry=r.castCounts[skillId] or {started=0,applied=0}; r.castCounts[skillId]=entry
        if applied then entry.applied+=1 else entry.started+=1 end
    end
end
function Report.Sample(dt: number)
    local r=current
    if not r then return end
    local effects=r.character:GetAttribute("ActiveSkillEffects")
    if type(effects)=="string" and effects~="" then
        r.debuffSeconds+=dt
        for _, effect in ipairs(string.split(effects," · ")) do r.effects[effect]=(r.effects[effect] or 0)+dt end
    end
    if not r.centerRangeSeconds then
        local a=r.character:FindFirstChild("RootCollider"); local b=r.target.PrimaryPart
        if a and a:IsA("BasePart") and b then
            local d=a.Position-b.Position
            if Vector3.new(d.X,0,d.Z).Magnitude<=math.max(1,number(r.character,"AttackRadius")) then r.centerRangeSeconds=os.clock()-r.started end
        end
    end
end
function Report.Outcome(): string?
    local r=current
    if not r then return nil end
    if r.character:GetAttribute("LifeState")~="Alive" then return "defeat" end
    if r.target:GetAttribute("HP")==0 then return "victory" end
    if not r.character.Parent or not r.target.Parent or r.player.Character~=r.character then return "interrupted" end
    if number(r.character,"RunSpeed")~=r.playerRunSpeed or number(r.character,"AttackSpeed")~=r.playerAS or number(r.character,"Damage")~=r.playerATK
        or number(r.target,"RunSpeed")~=r.monsterRunSpeed then return "interrupted" end
    if os.clock()-r.started>=90 then return "timeout" end
    return nil
end
function Report.Finish(outcome: string): any?
    local r=current; if not r then return nil end; current=nil
    local duration=math.max(.001,os.clock()-r.started)
    local effects={}; for name,seconds in pairs(r.effects) do effects[name]=round(seconds) end
    return {stage=r.stage, outcome=outcome, seconds=round(duration), damageDealt=r.dealt, damageReceived=r.received,
        dps=round(r.dealt/duration), incomingDps=round(r.received/duration), hpLeft=number(r.character,"HP"), maxHP=r.playerHP,
        targetHP=r.targetHP, targetHPLeft=number(r.target,"HP"), firstHitSeconds=r.firstHit and round(r.firstHit),
        firstCenterInRangeSeconds=r.centerRangeSeconds and round(r.centerRangeSeconds), attacks=r.attacks, hitCycles=r.hitCycles,
        fallbackAttacks=r.fallbackAttacks, timingOnly=r.fallbackAttacks>0,
        cyclesWithoutContact=math.max(0,r.attacks-r.hitCycles), hits=r.hits, crits=r.crits, headshots=r.headshots,
        incomingHits=r.incomingHits,incomingCrits=r.incomingCrits,periodicReceived=r.periodicReceived,
        debuffSeconds=round(r.debuffSeconds), effects=effects, casts=r.castCounts,
        playerAS=r.playerAS,playerATK=r.playerATK,playerRunSpeed=r.playerRunSpeed,
        monsterAS=r.monsterAS,monsterATK=r.monsterATK,monsterRunSpeed=r.monsterRunSpeed,
        playerRunStudsPerSecond=Movement.StudsPerSecond(nil,r.playerRunSpeed,"Run"),
        monsterRunStudsPerSecond=Movement.StudsPerSecond(nil,r.monsterRunSpeed,"Run"),
        animationSet=tostring(r.character:GetAttribute("AnimationWeaponSet") or ""), attackClips=r.clips,
        animationPreview=r.stage.weaponType=="dualswords" and r.character:GetAttribute("AnimationWeaponSet")=="1hs",
        equippedModel=tostring(r.character:GetAttribute("EquippedWeaponSlug") or "")}
end
function Report.EmitTrial(index: number, row: any)
    print("[game1][GP_TRIAL] "..HttpService:JSONEncode({index=index,result=row}))
end
function Report.EmitRetry(index: number)
    print("[game1][GP_TRIAL_RETRY] "..index)
end
function Report.Emit(results: {any}, version: string)
    print("[game1][GP_REPORT_BEGIN] "..version.." · "..#results)
    for i,row in ipairs(results) do print("[game1][GP_REPORT] "..HttpService:JSONEncode({index=i,result=row})) end
    local groups={}
    for _,row in ipairs(results) do
        if row.outcome=="skipped" then continue end
        local key=row.stage.weaponType.."/"..row.stage.monsterId
        if row.timingOnly then key..="/timing-only"
        elseif row.animationPreview then key..="/animation-preview" end
        local g=groups[key] or {count=0,wins=0,totalSeconds=0,totalDPS=0,winSeconds=0}
        groups[key]=g; g.count+=1; g.totalSeconds+=row.seconds; g.totalDPS+=row.dps
        if row.outcome=="victory" then g.wins+=1; g.winSeconds+=row.seconds end
    end
    local keys={}; for key in pairs(groups) do table.insert(keys,key) end; table.sort(keys)
    for _,key in ipairs(keys) do
        local g=groups[key]
        print("[game1][GP_SUMMARY] "..HttpService:JSONEncode({group=key,n=g.count,wins=g.wins,
            meanDPS=round(g.totalDPS/g.count),meanSeconds=round(g.totalSeconds/g.count),
            meanWinTTK=if g.wins>0 then round(g.winSeconds/g.wins) else nil}))
    end
    print("[game1][GP_REPORT_END]")
end
return table.freeze(Report)

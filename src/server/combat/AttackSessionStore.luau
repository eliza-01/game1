-- Per-player authoritative attack session state. No remotes, scheduling,
-- Workspace queries, weapon collision or damage effects live here.
local AttackSessionStore = {}

export type Session = {
    character: Model,
    serial: number,
    clientAttackId: number,
    untilTime: number,
    hitTargets: { [Model]: boolean },
    damageWindow: any?,
    headshotTarget: Model?,
    environmentBlocked: boolean,
    suppressedBounceLogged: boolean,
    sweepState: any?,
}

local byPlayer: { [Player]: Session } = {}

function AttackSessionStore.Get(player: Player): Session?
    return byPlayer[player]
end

function AttackSessionStore.IsCoolingDown(player: Player, now: number): boolean
    local session = byPlayer[player]
    return session ~= nil and now < session.untilTime
end

function AttackSessionStore.Begin(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    untilTime: number,
    damageWindow: any
): Session
    local session: Session = {
        character = character,
        serial = serial,
        clientAttackId = clientAttackId,
        untilTime = untilTime,
        hitTargets = {},
        damageWindow = damageWindow,
        headshotTarget = nil,
        environmentBlocked = false,
        suppressedBounceLogged = false,
        sweepState = nil,
    }
    byPlayer[player] = session
    return session
end

local function matches(session: Session?, character: Model, serial: number, clientAttackId: number): boolean
    return session ~= nil
        and session.character == character
        and session.serial == serial
        and session.clientAttackId == clientAttackId
end

function AttackSessionStore.HitTargets(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number
): { [Model]: boolean }?
    local session = byPlayer[player]
    if session and matches(session, character, serial, clientAttackId) then
        return session.hitTargets
    end
    return nil
end

function AttackSessionStore.HeadshotTarget(player: Player): Model?
    local session = byPlayer[player]
    return if session then session.headshotTarget else nil
end

function AttackSessionStore.SetHeadshotTarget(player: Player, target: Model?)
    local session = byPlayer[player]
    if session then
        session.headshotTarget = target
    end
end

-- Returns true exactly once per attack, to avoid logging every sweep substep.
function AttackSessionStore.FirstBounceSuppression(player: Player): boolean
    local session = byPlayer[player]
    if not session or session.suppressedBounceLogged then
        return false
    end
    session.suppressedBounceLogged = true
    return true
end

function AttackSessionStore.CanBounce(player: Player, character: Model, serial: number, clientAttackId: number): boolean
    local session = byPlayer[player]
    return session ~= nil and matches(session, character, serial, clientAttackId) and not session.environmentBlocked
end

function AttackSessionStore.BlockForBounce(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    untilTime: number
): boolean
    if not AttackSessionStore.CanBounce(player, character, serial, clientAttackId) then
        return false
    end
    local session = byPlayer[player]
    session.environmentBlocked = true
    session.damageWindow = nil
    session.sweepState = nil
    session.untilTime = untilTime
    return true
end

-- A delayed completion from an earlier attack cannot clear the next attack,
-- nor the session of a replacement character after respawn.
function AttackSessionStore.Finish(player: Player, character: Model, serial: number, clientAttackId: number): Session?
    local session = byPlayer[player]
    if not matches(session, character, serial, clientAttackId) then
        return nil
    end
    byPlayer[player] = nil
    return session
end

function AttackSessionStore.EnsureSweep(session: Session): any
    local sweep = session.sweepState
    if not sweep then
        sweep = {
            character = session.character,
            clientAttackId = session.clientAttackId,
        }
        session.sweepState = sweep
    end
    return sweep
end

function AttackSessionStore.CommitSweep(
    session: Session,
    sweep: any,
    elapsed: number,
    boxCFrame: CFrame,
    aimOrigin: Vector3?,
    aimDirection: Vector3?
)
    if session.sweepState ~= sweep then
        return
    end
    sweep.lastElapsed = elapsed
    sweep.lastBoxCFrame = boxCFrame
    sweep.lastAimOrigin = aimOrigin
    sweep.lastAimDirection = aimDirection
end

function AttackSessionStore.Forget(player: Player)
    byPlayer[player] = nil
end

return table.freeze(AttackSessionStore)

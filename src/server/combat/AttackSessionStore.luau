-- Per-player authoritative attack session state. No remotes, scheduling,
-- Workspace queries, weapon collision or damage effects live here.
local AttackSessionStore = {}

export type Session = {
    character: Model,
    serial: number,
    clientAttackId: number,
    untilTime: number,
    damageDealt: boolean,
    hitResolved: boolean,
    lastAimOrigin: Vector3?,
    lastAimDirection: Vector3?,
    attackFacingDirection: Vector3?,
    environmentBlocked: boolean,
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
    untilTime: number
): Session
    local session: Session = {
        character = character,
        serial = serial,
        clientAttackId = clientAttackId,
        untilTime = untilTime,
        damageDealt = false,
        hitResolved = false,
        lastAimOrigin = nil,
        lastAimDirection = nil,
        attackFacingDirection = nil,
        environmentBlocked = false,
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

function AttackSessionStore.SetAim(
    player: Player, character: Model, serial: number, clientAttackId: number,
    origin: Vector3?, direction: Vector3?
)
    local session = byPlayer[player]
    if matches(session, character, serial, clientAttackId)
        and typeof(origin) == "Vector3" and typeof(direction) == "Vector3" then
        session.lastAimOrigin = origin
        session.lastAimDirection = direction
        -- The last validated pre-HitEnd camera heading owns the attack sector.
        -- Locking this to the first packet made later swings strike behind cursor.
        session.attackFacingDirection = direction
    end
end

-- Consume exactly one authoritative damage event per attack session.
-- A delayed callback from another attack or respawn cannot resolve this one.
function AttackSessionStore.MarkMeleeResolved(
    player: Player, character: Model, serial: number, clientAttackId: number
): boolean
    local session = byPlayer[player]
    if not matches(session, character, serial, clientAttackId) or session.hitResolved then
        return false
    end
    session.hitResolved = true
    return true
end

function AttackSessionStore.MarkDamage(player: Player, character: Model, serial: number)
    local session = byPlayer[player]
    if session and session.character == character and session.serial == serial then
        session.damageDealt = true
    end
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

function AttackSessionStore.Forget(player: Player)
    byPlayer[player] = nil
end

return table.freeze(AttackSessionStore)

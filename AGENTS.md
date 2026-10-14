# Engineering rules — all game1 code

**Scope:** These rules apply to every language and surface in this repository: Luau (server/client/shared), Python, JavaScript, SQL, PowerShell, Studio plugins, generated manifests and test/support tooling. They are not specific to Roblox Studio. This document is the in-repository source of truth for future changes. Treat these rules as review criteria, not an excuse for an unsafe wholesale rewrite.

## Domain boundaries and ownership

1. **One clear responsibility per module.** A service coordinates a use case, not rendering + persistence + networking + validation + simulation in a single implementation. Split by responsibility, not arbitrary line count. A module exposes a small named public interface; its internal data and helper functions remain private.
2. **Depend inward.** Shared contracts and deterministic algorithms must not depend on server implementations, client UI or tooling. Server owns authoritative simulation, combat validation, progression, persistence and spawning. Client owns presentation, local input and visual interpolation. Editor/plugin/Host Agent own authoring; they must not become gameplay dependencies.
3. **Reuse through contracts, not copies.** Common actor navigation, facing, collision, hit validation, animation choice and equipment attachment belong in deliberately shared modules. Character / Monster / NPC adapters specify different policies and lifecycles. Avoid `if name == 'warsmith'`-style special cases and don't reuse a monster store's vocabulary as a public NPC API.
4. **Separate policy, orchestration and mechanisms.** Configuration describes *what* (weapon type, state, speed). A resolver picks policy. A mechanic executes. A presentation module renders. Avoid mixing all four.
5. **Explicit ownership of runtime state.** For each actor, declare which service is the sole writer of each state/attribute. Use intentional state transitions, not inferred timers that compete with AI or animation tracks. Subscriptions, tasks, connections, temporary instances and spawned NPCs must have cleanup ownership and be safe under respawn/reinit.
6. **Stable, versioned contracts.** Every HTTP endpoint, RemoteEvent/RemoteFunction payload, Studio Bridge command and registry schema has documented identity, validation, schema version, error semantics and compatibility policy. Prefer thin transport adapters → application services → repositories. A handler must not directly own unrelated domains.
7. **One source of truth for data.** Use explicit migrations for SQLite and generated manifests; maintain backward compatibility or an idempotent upgrade path. Preserve identity and published IDs unless the user intentionally changes them. Generated content must be reproducible and must not silently overwrite editor-owned data. No secrets, media or heavyweight assets in diagnostics.
8. **Security and failure isolation.** Validate all untrusted input, particularly client-supplied combat data and Host Agent/Studio commands. Restrict debug mutations to Studio. Use least privilege, bounded work and timeouts. An optional debug service or single NPC should not prevent unrelated server services from starting. No arbitrary filesystem reads from web paths.
9. **Performance at MMORPG scale.** Avoid per-actor full-Workspace scans, unnecessary per-frame remote messages, creation of new tracks or physics constraints in tight loops, and unbounded registries. Define caches, memory/network budgets and cleanup. Explicitly distinguish server simulation rate from client render interpolation.
10. **Code review quality bar.** Descriptive names, strict Luau types where possible, pure helpers for calculations, narrow constructor inputs/dependency injection for testing, short cohesive files, no dead workarounds or hidden fallback behavior. Document intentional compatibility exceptions with ownership and removal plan.

## Required change workflow

1. Read current sources and contracts, identify the minimal responsible modules, and define observable acceptance criteria *before* touching runtime.
2. Separate behavior-preserving extraction from behavior changes. Never rewrite combat movement, animation and storage in one step without isolation tests.
3. Add or update focused unit and contract tests. Include real behavior/transition cases where possible; source-string assertions alone are insufficient. Test all affected entity types and the published game versus Studio-only mode.
4. For data changes, write reversible/idempotent migrations, create backup, test upgrade on a copy of actual manifests/SQLite data, and show rollback or recovery procedures.
5. Run `python system/verify/verify.py` and `python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q`, plus language/tool-specific checks. For movement/physics/animation/network changes, do a Roblox Studio Play regression; static tests cannot validate these.
6. Verify `git apply --check` against the actual supplied project version. Deliver changes as a patch from the game1 project root with one single PowerShell block; restart **only** services affected. Do not restart Rojo or open new consoles by default.
7. In every handoff describe boundaries changed, migrations, observed tests, untested runtime scenarios and any regressions/risks. Never claim full Studio validation from static tests.

## Planned decomposition (not yet implemented)

See `docs/ARCHITECTURE_AUDIT_2026-10-14_RU.md` for priority and exact targets. The existing large files are **not exempt** from these rules; refactor incrementally, maintaining observable behavior.

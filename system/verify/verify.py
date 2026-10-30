from pathlib import Path
import sys

from validators.actor_runtime import check_actor_runtime_contracts
from validators.combat_foundation import check_combat_foundation
from validators.hitbox_runtime import check_hitbox_runtime
from validators.studio_character_bridge import check_studio_character_bridge
from validators.registered_attack_clips import check_registered_attack_clips
from validators.deco_studio import check_deco_studio
from validators.environment_bounce import check_environment_bounce
from validators.location_authoring import check_location_authoring
from validators.location_assets import check_location_assets_core
from validators.location_asset_categories import check_location_asset_categories
from validators.location_asset_variants import check_location_asset_variants
from validators.location_texture_sync import check_location_texture_sync
from validators.attack_timelines import check_attack_timelines
from validators.authoring_tooling import check_authoring_tooling
from validators.death_runtime import check_death_runtime
from validators.studio_debug import check_studio_debug
from validators.animations import check_animation_scaling, check_character_animation, check_manual_animation_reimport
from validators.characters import (
    check_character_manifest, check_character_rig, check_character_publication,
    check_character_identity, check_character_starting_stats,
)
from validators.weapons import check_weapon_registration, check_weapon_attack_movement
from validators.combat_contact import check_combat_contact_contracts
from validators.monsters import check_monster_contracts
from validators.project_layout import check_project_identity, check_project_layout
from validators.source_only import check_source_only_contract

ROOT = Path(__file__).resolve().parents[2]
errors = []


def err(message: str) -> None:
    errors.append(message)


# M165: project identity is checked before archetype data for stable diagnostics.
check_project_identity(ROOT, err)

archetypes, active_id = check_character_manifest(ROOT, err)

# M165: project layout, forbidden legacy references, and runtime inventory.
check_project_layout(ROOT, err)

(attack_text, damage_resolver_text, attack_timeline_text, attack_timeline_data_text) = check_combat_foundation(ROOT, err)

character_service_text, rig_text = check_character_rig(ROOT, err)

hitbox_implementation_text = check_hitbox_runtime(ROOT, err)

plugin_text, host_agent_text = check_studio_character_bridge(ROOT, err)

schema_text, ui, js, character_js_text = check_character_publication(
    ROOT, err, host_agent_text=host_agent_text, plugin_text=plugin_text, archetypes=archetypes,
)


(
    animation_store_text, animation_registry_text, controller_runtime,
    client_init_text, attack_controller_text, movement_runtime, js_text,
) = check_character_animation(
    ROOT, err, schema_text=schema_text, ui=ui, js=js, character_service_text=character_service_text,
)

check_character_identity(ROOT, err, schema_text=schema_text, ui=ui, host_agent_text=host_agent_text, js_text=js_text)

stats_config_text, stats_service_text, movement_config_text = check_weapon_registration(
    ROOT, err, schema_text=schema_text, ui=ui, host_agent_text=host_agent_text,
    plugin_text=plugin_text, rig_text=rig_text, character_service_text=character_service_text,
    attack_text=attack_text, controller_runtime=controller_runtime,
    attack_controller_text=attack_controller_text, client_init_text=client_init_text,
)

server_init_text = check_studio_debug(
    ROOT, err, plugin_text=plugin_text,
    stats_service_text=stats_service_text, client_init_text=client_init_text,
)


# m12 shared animation-speed scaling: gameplay stat -> playback percentage
check_animation_scaling(
    ROOT, err, ui=ui, host_agent_text=host_agent_text, character_js_text=character_js_text,
    animation_registry_text=animation_registry_text, attack_timeline_text=attack_timeline_text,
)


monster_sources = check_monster_contracts(
    ROOT, err, schema_text=schema_text, host_agent_text=host_agent_text,
    plugin_text=plugin_text, ui=ui, server_init_text=server_init_text,
    stats_config_text=stats_config_text, stats_service_text=stats_service_text,
    animation_store_text=animation_store_text,
)

character_service_text = check_death_runtime(
    ROOT, err, animation_store_text=animation_store_text,
    monster_sources=monster_sources, damage_resolver_text=damage_resolver_text,
)

check_registered_attack_clips(ROOT, err, attack_timeline_data_text=attack_timeline_data_text)

check_character_starting_stats(ROOT, err, character_service_text=character_service_text, stats_service_text=stats_service_text)

studio_plugin_text = check_manual_animation_reimport(
    ROOT, err, animation_store_text=animation_store_text,
    character_js_text=character_js_text, host_agent_text=host_agent_text,
)

check_weapon_attack_movement(ROOT, err, host_agent_text=host_agent_text)

check_actor_runtime_contracts(
    ROOT, err, monster_attributes_text=monster_sources.attributes_text,
    monster_runtime_text=monster_sources.runtime_text,
)

check_combat_contact_contracts(
    ROOT, err, damage_resolver_text=damage_resolver_text,
    hitbox_implementation_text=hitbox_implementation_text,
)

index_m35_text, studio_bridge_m35_text = check_attack_timelines(
    ROOT, err, attack_timeline_text=attack_timeline_text,
    attack_timeline_data_text=attack_timeline_data_text,
    studio_plugin_text=studio_plugin_text, host_agent_text=host_agent_text,
)


check_authoring_tooling(ROOT, err)


check_location_authoring(
    ROOT, err, index_text=index_m35_text, host_agent_text=host_agent_text,
    studio_bridge_text=studio_bridge_m35_text, studio_plugin_text=studio_plugin_text,
)

location_assets = check_location_assets_core(
    ROOT, err, host_agent_text=host_agent_text, studio_plugin_text=studio_plugin_text,
)

check_deco_studio(
    ROOT, err, sources=location_assets, host_agent_text=host_agent_text,
    studio_plugin_text=studio_plugin_text,
)

check_location_asset_variants(
    ROOT, err, sources=location_assets, host_agent_text=host_agent_text,
    studio_plugin_text=studio_plugin_text,
)

environment_asset_service_text, install_plugin_text = check_environment_bounce(
    ROOT, err, sources=location_assets, host_agent_text=host_agent_text,
    studio_plugin_text=studio_plugin_text,
)

check_location_texture_sync(
    ROOT, err, sources=location_assets,
    environment_asset_service_text=environment_asset_service_text,
)

# M164: M52/M53 source-only invariants now live in one read-only validator.
check_source_only_contract(
    ROOT, err,
    location_asset_store_text=location_assets.store_text,
    deco_assets_js_text=location_assets.assets_js,
    host_agent_text=host_agent_text,
    character_js_text=character_js_text,
    ui_html=ui,
)

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

check_location_asset_categories(
    ROOT, err, sources=location_assets, character_js_text=character_js_text,
    studio_plugin_text=studio_plugin_text, install_plugin_text=install_plugin_text,
)

print("verify ok · game1 m55 Buildings + synchronized Location Asset category context passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("race pool: human")
print("gender pool: male, female")
print("canonical place: place/game1.rbxl")

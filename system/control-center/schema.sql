create table if not exists characters (
    id text primary key,
    display_name text not null,
    race text not null default '',
    gender text not null default '',
    source_path text not null default '',
    prepared_path text not null default '',
    sha256 text not null default '',
    model_asset_id text,
    status text not null default 'INCOMPLETE',
    revision integer not null default 1,
    created_at real not null,
    updated_at real not null,
    armature_name text not null default '',
    bone_count integer not null default 0,
    mesh_count integer not null default 0,
    skeleton_signature text not null default '',
    skeleton_structure_signature text not null default '',
    skeleton_json text not null default '{}',
    published_sha256 text not null default '',
    moderation_state text not null default '',
    published_at real
);

create table if not exists project_settings (
    key text primary key,
    value text not null default ''
);

create table if not exists character_publications (
    id integer primary key autoincrement,
    character_id text not null,
    character_revision integer not null,
    asset_id text not null,
    operation_path text not null,
    sha256 text not null,
    moderation_state text,
    published_at real not null
);

create table if not exists character_model_assignments (
    id integer primary key autoincrement,
    target_character_id text not null,
    source_character_id text not null,
    asset_id text not null default '',
    assigned_at real not null
);

create table if not exists animation_profiles (
    character_id text primary key,
    skeleton_signature text not null default '',
    scan_root text not null default '',
    created_at real not null,
    updated_at real not null
);

create table if not exists animation_clips (
    id text primary key,
    character_id text not null,
    name text not null,
    source_path text not null,
    prepared_path text not null,
    sha256 text not null,
    asset_id text,
    published_sha256 text not null default '',
    moderation_state text not null default '',
    revision integer not null default 1,
    created_at real not null,
    updated_at real not null,
    published_at real
);

create table if not exists animation_bindings (
    id text primary key,
    character_id text not null,
    scope text not null,
    weapon_set text not null default '',
    slot text not null,
    variant integer not null default 0,
    clip_id text not null,
    weight integer not null default 100,
    looped integer not null default 0,
    priority text not null default 'Movement',
    created_at real not null,
    updated_at real not null,
    unique(character_id, scope, weapon_set, slot, variant)
);

create table if not exists animation_publications (
    id integer primary key autoincrement,
    clip_id text not null,
    clip_revision integer not null,
    asset_id text not null,
    operation_path text not null,
    sha256 text not null,
    moderation_state text,
    published_at real not null
);

create table if not exists weapons (
    slug text primary key,
    name_en text not null,
    name_ru text not null default '',
    weapon_type text not null,
    rarity text not null,
    model_source_path text not null default '',
    model_prepared_path text not null default '',
    model_sha256 text not null default '',
    model_asset_id text,
    model_published_sha256 text not null default '',
    moderation_state text not null default '',
    revision integer not null default 1,
    created_at real not null,
    updated_at real not null,
    published_at real
);

create table if not exists weapon_textures (
    id text primary key,
    weapon_slug text not null,
    slot text not null,
    source_path text not null,
    prepared_path text not null,
    sha256 text not null,
    asset_id text,
    published_sha256 text not null default '',
    moderation_state text not null default '',
    revision integer not null default 1,
    created_at real not null,
    updated_at real not null,
    published_at real,
    unique(weapon_slug, slot)
);

create table if not exists weapon_stat_modifiers (
    weapon_slug text not null,
    stat_key text not null,
    delta real not null default 0,
    primary key(weapon_slug, stat_key)
);

create table if not exists weapon_publications (
    id integer primary key autoincrement,
    weapon_slug text not null,
    kind text not null,
    slot text not null default '',
    weapon_revision integer not null,
    asset_id text not null,
    operation_path text not null,
    sha256 text not null,
    moderation_state text,
    published_at real not null
);

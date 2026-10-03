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

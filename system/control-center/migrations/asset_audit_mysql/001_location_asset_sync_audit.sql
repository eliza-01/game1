CREATE TABLE IF NOT EXISTS asset_replacement_operations (
    audit_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    operation_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    occurred_at_utc DATETIME(6) NOT NULL,
    event_kind VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    asset_domain VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    asset_key VARCHAR(255) NOT NULL,
    asset_slot VARCHAR(128) NOT NULL DEFAULT '',
    asset_type VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    source_system VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    source_record VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT '',
    operation_path VARCHAR(512) NOT NULL DEFAULT '',
    metadata_json JSON NOT NULL,
    binding_revision BIGINT UNSIGNED NOT NULL,
    matched_instances INT UNSIGNED NOT NULL,
    changed_instances INT UNSIGNED NOT NULL,
    changed_parts INT UNSIGNED NOT NULL,
    pending_geometry INT UNSIGNED NOT NULL,
    PRIMARY KEY (audit_id),
    UNIQUE KEY uq_asset_replacement_operation (operation_id),
    UNIQUE KEY uq_asset_replacement_source (source_system, source_record),
    KEY ix_asset_replacement_identity (asset_domain, asset_key, audit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS asset_replacement_changes (
    operation_audit_id BIGINT UNSIGNED NOT NULL,
    change_ordinal SMALLINT UNSIGNED NOT NULL,
    change_kind VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    old_asset_id VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    new_asset_id VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    changed_count INT UNSIGNED NOT NULL,
    PRIMARY KEY (operation_audit_id, change_ordinal),
    CONSTRAINT fk_asset_replacement_changes_operation
        FOREIGN KEY (operation_audit_id) REFERENCES asset_replacement_operations(audit_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS asset_replacement_instances (
    operation_audit_id BIGINT UNSIGNED NOT NULL,
    instance_ordinal INT UNSIGNED NOT NULL,
    instance_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    studio_path VARCHAR(1024) NOT NULL,
    PRIMARY KEY (operation_audit_id, instance_ordinal),
    UNIQUE KEY uq_asset_replacement_instance (operation_audit_id, instance_id),
    CONSTRAINT fk_asset_replacement_instances_operation
        FOREIGN KEY (operation_audit_id) REFERENCES asset_replacement_operations(audit_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS asset_replacement_instance_changes (
    operation_audit_id BIGINT UNSIGNED NOT NULL,
    instance_ordinal INT UNSIGNED NOT NULL,
    change_ordinal SMALLINT UNSIGNED NOT NULL,
    change_kind VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    old_asset_id VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    new_asset_id VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    changed_count INT UNSIGNED NOT NULL,
    PRIMARY KEY (operation_audit_id, instance_ordinal, change_ordinal),
    CONSTRAINT fk_asset_replacement_instance_changes_instance
        FOREIGN KEY (operation_audit_id, instance_ordinal)
        REFERENCES asset_replacement_instances(operation_audit_id, instance_ordinal)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

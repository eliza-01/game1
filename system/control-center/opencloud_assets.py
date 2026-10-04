from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib import error, request
import json
import time
import uuid

CREATE_ASSET_URL = "https://apis.roblox.com/assets/v1/assets"
UPDATE_ASSET_URL_TEMPLATE = "https://apis.roblox.com/assets/v1/assets/{asset_id}"
OPERATION_URL_TEMPLATE = "https://apis.roblox.com/assets/v1/operations/{operation_id}"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class OpenCloudAssetError(RuntimeError):
    pass


@dataclass(frozen=True)
class UploadResult:
    operation_path: str
    asset_id: str
    revision_id: str | None
    moderation_state: str | None


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener():
    return request.build_opener(_NoRedirect())


def _creator_payload(creator_type: str, creator_id: str) -> dict:
    creator_type = creator_type.strip().lower()
    creator_id = creator_id.strip()
    if not creator_id.isdigit() or int(creator_id) <= 0:
        raise OpenCloudAssetError("ROBLOX_CREATOR_ID must be a positive numeric id")
    if creator_type == "user":
        return {"userId": creator_id}
    if creator_type == "group":
        return {"groupId": creator_id}
    raise OpenCloudAssetError("ROBLOX_CREATOR_TYPE must be user or group")


def _multipart(metadata: dict, file_path: Path, content_type: str) -> tuple[bytes, str]:
    boundary = f"----game1assetmanager{uuid.uuid4().hex}"
    marker = boundary.encode("ascii")
    request_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    file_bytes = file_path.read_bytes()
    safe_name = file_path.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    body = b"".join(
        [
            b"--" + marker + b"\r\n"
            b'Content-Disposition: form-data; name="request"\r\n'
            b"Content-Type: application/json; charset=utf-8\r\n\r\n"
            + request_json
            + b"\r\n",
            b"--" + marker + b"\r\n"
            + f'Content-Disposition: form-data; name="fileContent"; filename="{safe_name}"\r\n'.encode("utf-8")
            + f"Content-Type: {content_type}\r\n\r\n".encode("ascii")
            + file_bytes
            + b"\r\n",
            b"--" + marker + b"--\r\n",
        ]
    )
    return body, boundary


def _json_http(req: request.Request, timeout: float) -> dict:
    try:
        with _opener().open(req, timeout=timeout) as response:
            raw = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OpenCloudAssetError(f"roblox open cloud http {exc.code}: {detail[:4000]}") from exc
    except error.URLError as exc:
        raise OpenCloudAssetError(f"roblox open cloud request failed: {exc.reason}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise OpenCloudAssetError(f"roblox open cloud returned invalid json: {raw[:1000]!r}") from exc
    if not isinstance(value, dict):
        raise OpenCloudAssetError("roblox open cloud returned a non-object response")
    return value


def _validate_upload(file_path: Path, api_key: str):
    file_path = file_path.resolve()
    if not file_path.is_file() or file_path.suffix.lower() != ".fbx":
        raise OpenCloudAssetError("character publication requires a canonical FBX")
    size = file_path.stat().st_size
    if size <= 0:
        raise OpenCloudAssetError("character FBX is empty")
    if size > MAX_UPLOAD_BYTES:
        raise OpenCloudAssetError(f"character FBX is larger than 20 MB: {size} bytes")
    if not api_key.strip():
        raise OpenCloudAssetError("ROBLOX_OPEN_CLOUD_API_KEY is not configured in .env.local")


def create_model_asset(
    file_path: Path,
    *,
    display_name: str,
    description: str,
    creator_type: str,
    creator_id: str,
    api_key: str,
) -> str:
    _validate_upload(file_path, api_key)
    metadata = {
        "assetType": "Model",
        "displayName": display_name.strip(),
        "description": description,
        "creationContext": {"creator": _creator_payload(creator_type, creator_id)},
    }
    body, boundary = _multipart(metadata, file_path, "model/fbx")
    req = request.Request(
        CREATE_ASSET_URL,
        data=body,
        headers={
            "x-api-key": api_key.strip(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Accept": "application/json",
            "User-Agent": "game1-asset-manager/0.3",
        },
        method="POST",
    )
    response = _json_http(req, 120.0)
    operation = str(response.get("path") or "").strip()
    if not operation.startswith("operations/"):
        raise OpenCloudAssetError("create asset returned no operation path")
    return operation


def update_model_asset(
    file_path: Path,
    *,
    asset_id: str,
    display_name: str,
    description: str,
    creator_type: str,
    creator_id: str,
    api_key: str,
) -> str:
    _validate_upload(file_path, api_key)
    asset_id = str(asset_id or "").strip()
    if not asset_id.isdigit() or int(asset_id) <= 0:
        raise OpenCloudAssetError("model asset id must be numeric before update")
    metadata = {
        "assetType": "Model",
        "assetId": asset_id,
        "displayName": display_name.strip(),
        "description": description,
        "creationContext": {"creator": _creator_payload(creator_type, creator_id)},
    }
    body, boundary = _multipart(metadata, file_path, "model/fbx")
    req = request.Request(
        UPDATE_ASSET_URL_TEMPLATE.format(asset_id=asset_id),
        data=body,
        headers={
            "x-api-key": api_key.strip(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Accept": "application/json",
            "User-Agent": "game1-asset-manager/0.3",
        },
        method="PATCH",
    )
    response = _json_http(req, 120.0)
    operation = str(response.get("path") or "").strip()
    if not operation.startswith("operations/"):
        raise OpenCloudAssetError("update asset returned no operation path")
    return operation



def _validate_animation_upload(file_path: Path, api_key: str):
    file_path = file_path.resolve()
    if not file_path.is_file() or file_path.suffix.lower() not in {".rbxm", ".rbxmx"}:
        raise OpenCloudAssetError("animation publication requires a Studio-exported RBXM or RBXMX")
    size = file_path.stat().st_size
    if size <= 0:
        raise OpenCloudAssetError("animation file is empty")
    if size > MAX_UPLOAD_BYTES:
        raise OpenCloudAssetError(f"animation file is larger than 20 MB: {size} bytes")
    if not api_key.strip():
        raise OpenCloudAssetError("ROBLOX_OPEN_CLOUD_API_KEY is not configured in .env.local")


def create_animation_asset(
    file_path: Path,
    *,
    display_name: str,
    description: str,
    creator_type: str,
    creator_id: str,
    api_key: str,
) -> str:
    _validate_animation_upload(file_path, api_key)
    metadata = {
        "assetType": "Animation",
        "displayName": display_name.strip(),
        "description": description,
        "creationContext": {"creator": _creator_payload(creator_type, creator_id)},
    }
    body, boundary = _multipart(metadata, file_path, "model/x-rbxm")
    req = request.Request(
        CREATE_ASSET_URL,
        data=body,
        headers={
            "x-api-key": api_key.strip(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Accept": "application/json",
            "User-Agent": "game1-asset-manager/0.5",
        },
        method="POST",
    )
    response = _json_http(req, 120.0)
    operation = str(response.get("path") or "").strip()
    if not operation.startswith("operations/"):
        raise OpenCloudAssetError("create animation asset returned no operation path")
    return operation


def get_operation(operation_path: str, *, api_key: str) -> dict:
    operation_id = operation_path.rstrip("/").split("/")[-1].strip()
    if not operation_id:
        raise OpenCloudAssetError("operation path is invalid")
    req = request.Request(
        OPERATION_URL_TEMPLATE.format(operation_id=operation_id),
        headers={
            "x-api-key": api_key.strip(),
            "Accept": "application/json",
            "User-Agent": "game1-asset-manager/0.3",
        },
        method="GET",
    )
    return _json_http(req, 30.0)


def wait_for_operation(operation_path: str, *, api_key: str, timeout_seconds: float = 180.0) -> UploadResult:
    deadline = time.monotonic() + timeout_seconds
    while True:
        operation = get_operation(operation_path, api_key=api_key)
        if operation.get("done") is True:
            if operation.get("error"):
                raise OpenCloudAssetError("roblox rejected the asset: " + json.dumps(operation["error"], ensure_ascii=False))
            response = operation.get("response") or {}
            asset_id = str(response.get("assetId") or "").strip()
            if not asset_id.isdigit():
                raise OpenCloudAssetError("operation completed without a numeric asset id")
            moderation = response.get("moderationResult") or {}
            return UploadResult(
                operation_path=operation_path,
                asset_id=asset_id,
                revision_id=str(response.get("revisionId")) if response.get("revisionId") is not None else None,
                moderation_state=str(moderation.get("moderationState")) if moderation.get("moderationState") is not None else None,
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(f"roblox did not finish {operation_path} within {timeout_seconds:.0f}s")
        time.sleep(2.0)

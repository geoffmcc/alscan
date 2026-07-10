# SPDX-License-Identifier: GPL-3.0-only
"""Merge manifest — serializable container for the complete guided merge session and plan."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from alscan import __version__
from alscan.merge.session import MergeSession
from alscan.merge.operation import (
    MergeOperation,
    ExecutionMode,
    OperationState,
    RiskLevel,
    SupportClassification,
    ActivityCategory,
)

MANIFEST_FORMAT_VERSION = "1"


@dataclass
class MergeManifest:
    document_type: str = "alscan-merge-manifest"
    format_version: str = MANIFEST_FORMAT_VERSION
    alscan_version: str = __version__
    created_at_utc: str = ""
    updated_at_utc: str = ""

    session: dict = field(default_factory=dict)
    operations: list[dict] = field(default_factory=list)
    source_hashes_captured: dict[str, str] = field(default_factory=dict)
    source_hashes_final: dict[str, str] = field(default_factory=dict)
    verification_summary: dict = field(default_factory=dict)

    _session_obj: MergeSession | None = field(default=None, repr=False, compare=False)
    _operations_obj: list[MergeOperation] | None = field(default=None, repr=False, compare=False)

    @classmethod
    def create(
        cls,
        session: MergeSession,
        operations: list[MergeOperation] | None = None,
    ) -> MergeManifest:
        manifest = cls(
            created_at_utc=session.created_at_utc,
            session=session.to_dict(),
            operations=[op.to_dict() for op in (operations or [])],
        )
        manifest._session_obj = session
        manifest._operations_obj = operations or []
        return manifest

    def get_session(self) -> MergeSession:
        if self._session_obj is None:
            self._session_obj = MergeSession(**self.session)
        return self._session_obj

    def get_operations(self) -> list[MergeOperation]:
        if self._operations_obj is None:
            self._operations_obj = [
                _deserialize_operation(op) for op in self.operations
            ]
        return self._operations_obj

    def sync_from_objects(self) -> None:
        session = self.get_session()
        operations = self.get_operations()
        self.session = session.to_dict()
        self.operations = [op.to_dict() for op in operations]
        self.updated_at_utc = _utc_now()

    def to_json(self) -> str:
        self.sync_from_objects()
        d = asdict(self, dict_factory=_manifest_dict_factory)
        d.pop("_session_obj", None)
        d.pop("_operations_obj", None)
        return json.dumps(d, indent=2, ensure_ascii=False, allow_nan=False, sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> MergeManifest:
        d = json.loads(data)
        if d.get("document_type") != "alscan-merge-manifest":
            raise ValueError(
                f"Expected alscan-merge-manifest document, got '{d.get('document_type')}'"
            )
        version = str(d.get("format_version", ""))
        if version != MANIFEST_FORMAT_VERSION:
            if _version_is_future(version):
                raise ValueError(
                    f"Manifest format version {version} is from a newer alscan version. "
                    f"This version supports format {MANIFEST_FORMAT_VERSION}."
                )
        manifest = cls(
            document_type=d.get("document_type", "alscan-merge-manifest"),
            format_version=str(d.get("format_version", MANIFEST_FORMAT_VERSION)),
            alscan_version=d.get("alscan_version", ""),
            created_at_utc=d.get("created_at_utc", ""),
            updated_at_utc=d.get("updated_at_utc", ""),
            session=d.get("session", {}),
            operations=d.get("operations", []),
            source_hashes_captured=d.get("source_hashes_captured", {}),
            source_hashes_final=d.get("source_hashes_final", {}),
            verification_summary=d.get("verification_summary", {}),
        )
        try:
            manifest._session_obj = MergeSession(**manifest.session)
        except TypeError as e:
            manifest._session_obj = None
            import warnings
            warnings.warn(
                f"Manifest session data is incompatible with alscan "
                f"{__version__}. Some session methods may fail: {e}",
                RuntimeWarning,
                stacklevel=2,
            )
        return manifest

    def redacted_copy(self) -> MergeManifest:
        d = json.loads(self.to_json())
        d = _redact_manifest(d)
        return MergeManifest.from_json(json.dumps(d))


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _version_is_future(version: str) -> bool:
    try:
        return int(version) > int(MANIFEST_FORMAT_VERSION)
    except ValueError:
        return True


def _manifest_dict_factory(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        if key.startswith("_"):
            continue
        if isinstance(value, type):
            continue
        if key == "_manifest_dict_factory":
            continue
        result[key] = value
    return result


def _redact_manifest(d: dict) -> dict:
    redacted = {}
    for key, value in d.items():
        if key == "session" and isinstance(value, dict):
            redacted[key] = _redact_session(value)
        elif key == "source_hashes_captured":
            redacted[key] = {k: "[redacted]" for k in value}
        elif key == "source_hashes_final":
            redacted[key] = {k: "[redacted]" for k in value}
        elif isinstance(value, dict):
            redacted[key] = _redact_manifest(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_manifest(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def _redact_session(s: dict) -> dict:
    redacted = dict(s)
    sources = redacted.get("sources", {})
    if isinstance(sources, dict):
        redacted["sources"] = {}
        for role, src in sources.items():
            if isinstance(src, dict):
                redacted_src = dict(src)
                redacted_src["path"] = "[redacted path]"
                redacted_src["resolved"] = "[redacted path]"
                redacted_src["label"] = "[redacted label]"
                redacted["sources"][role] = redacted_src
            else:
                redacted["sources"][role] = src
    return redacted


def _deserialize_operation(d: dict) -> MergeOperation:
    result = dict(d)
    for field, enum_cls in [
        ("category", ActivityCategory),
        ("state", OperationState),
        ("execution_mode", ExecutionMode),
        ("risk_level", RiskLevel),
        ("support_classification", SupportClassification),
    ]:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = enum_cls(result[field])
            except ValueError:
                raise ValueError(
                    f"Unknown {field} value '{result[field]}' in manifest operation "
                    f"'{result.get('operation_id', 'unknown')}'. "
                    f"Valid values: {[e.value for e in enum_cls]}"
                ) from None
    return MergeOperation(**result)

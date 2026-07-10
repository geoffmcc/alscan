# SPDX-License-Identifier: GPL-3.0-only
"""Systematic ID allocation for synthetic .als fixture generation.

Ensures every generated list member that requires an Id attribute receives
a unique, deterministic value. Validates referential integrity before
serialization.

This module only supports synthetic fixture generation. It is NOT used
for reading or writing real Ableton-authored Sets.
"""

from __future__ import annotations

from collections import defaultdict


class IdAllocator:
    """Allocates unique, deterministic IDs for synthetic fixture elements.

    Tracks allocation scopes so that IDs are unique within their container
    (e.g., track IDs within <Tracks>, clip IDs within a track's ClipSlotList).
    """

    def __init__(self) -> None:
        self._next_id: int = 0
        self._reserved: set[int] = set()
        self._allocated: dict[str, list[int]] = defaultdict(list)
        self._references: dict[int, list[str]] = defaultdict(list)
        self._id_to_scope: dict[int, str] = {}

    def reserve(self, ids: set[int]) -> None:
        """Reserve specific IDs (e.g., sentinel values like -1)."""
        self._reserved |= ids

    def allocate(self, scope: str = "global") -> int:
        """Allocate the next available unique ID for the given scope."""
        while self._next_id in self._reserved:
            self._next_id += 1
        oid = self._next_id
        self._next_id += 1
        self._allocated[scope].append(oid)
        self._id_to_scope[oid] = scope
        return oid

    def allocate_specific(self, oid: int, scope: str = "global") -> None:
        """Claim a specific ID value for the given scope."""
        if oid in self._reserved and oid not in self._id_to_scope:
            raise ValueError(
                f"ID {oid} is reserved and cannot be allocated."
            )
        if oid in self._id_to_scope:
            raise ValueError(
                f"ID {oid} is already allocated in scope "
                f"'{self._id_to_scope[oid]}'."
            )
        self._allocated[scope].append(oid)
        self._id_to_scope[oid] = scope
        if oid >= self._next_id:
            self._next_id = oid + 1

    def register_reference(self, ref_id: int, label: str) -> None:
        """Record that something references an allocated ID."""
        if ref_id in self._id_to_scope:
            self._references[ref_id].append(label)
        else:
            raise ValueError(
                f"Reference to unallocated ID {ref_id} from '{label}'."
            )

    def get_ids_in_scope(self, scope: str) -> list[int]:
        return list(self._allocated.get(scope, []))

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty list means valid."""
        errors = []

        for scope, ids in self._allocated.items():
            seen = set()
            for oid in ids:
                if oid in seen:
                    errors.append(
                        f"Duplicate ID {oid} in scope '{scope}'."
                    )
                seen.add(oid)

        for ref_id, labels in self._references.items():
            if ref_id not in self._id_to_scope:
                errors.append(
                    f"Dangling reference to ID {ref_id} from "
                    f"{', '.join(labels)}."
                )

        return errors

    def reset_scoped(self, scope: str) -> None:
        """Reset allocations for a scope (useful for per-track clip IDs)."""
        for oid in list(self._allocated.get(scope, [])):
            if oid in self._id_to_scope and self._id_to_scope[oid] == scope:
                del self._id_to_scope[oid]
        self._allocated[scope] = []

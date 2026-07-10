# SPDX-License-Identifier: GPL-3.0-only
"""Global pointee ID allocator for synthetic Live 12.4.2 fixture generation.

Manages the allocation of <Pointee Id="N"/> elements and validates
that NextPointeeId is consistent with the complete object graph.

Separate from the member IdAllocator (which handles track IDs, clip IDs, etc.).
"""

from __future__ import annotations


class PointeeAllocator:
    """Allocates unique, sequential global pointee IDs.

    Live 12.4.2 uses <Pointee Id="N"/> self-closing elements to allocate
    pointee slots. Every object that needs a pointee identity (tracks,
    devices, the LiveSet itself, scenes, etc.) consumes one pointee ID.

    <PointeeId Value="N"/> elements (inside EnvelopeTarget) reference
    these allocated pointees.

    NextPointeeId must be strictly greater than the highest allocated
    Pointee Id. Zero is a reserved/sentinel value. Allocation starts at 1.
    """

    def __init__(self) -> None:
        self._next: int = 1
        self._allocated: list[int] = []
        self._labels: list[str] = []
        self._validated: bool = False

    def allocate(self, label: str) -> int:
        """Allocate the next pointee ID. Returns the allocated value."""
        if self._validated:
            raise RuntimeError("Cannot allocate after finalization.")
        oid = self._next
        self._next += 1
        self._allocated.append(oid)
        self._labels.append(label)
        return oid

    def allocate_batch(self, count: int, label_prefix: str) -> list[int]:
        """Allocate multiple pointee IDs at once."""
        return [self.allocate(f"{label_prefix}[{i}]") for i in range(count)]

    def pointee_element(self, oid: int) -> str:
        """Return the XML for a <Pointee Id="N"/> allocation element."""
        return f'<Pointee Id="{oid}"/>'

    def next_pointee_id(self) -> int:
        """Return the NextPointeeId value for the root LiveSet."""
        return self._next

    def finalize(self) -> None:
        """Mark the allocator as finalized. No more allocations allowed."""
        self._validated = True

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty list means valid."""
        errors = []
        if len(self._allocated) == 0:
            errors.append("No pointee IDs allocated. NextPointeeId would be 1.")
        seen = set()
        for oid in self._allocated:
            if oid in seen:
                errors.append(f"Duplicate pointee ID: {oid}")
            seen.add(oid)
        if self._next <= max(self._allocated) if self._allocated else False:
            errors.append(
                f"NextPointeeId={self._next} is not greater than "
                f"max allocated={max(self._allocated)}"
            )
        return errors

    def summary(self) -> str:
        return (
            f"PointeeAllocator: {len(self._allocated)} allocated, "
            f"range=[{self._allocated[0] if self._allocated else 0}.."
            f"{self._allocated[-1] if self._allocated else 0}], "
            f"NextPointeeId={self._next}"
        )

# SPDX-License-Identifier: GPL-3.0-only
"""Progressive automation architecture — pluggable operation executors.

ALL WRITING IS CURRENTLY DISABLED. Guided Merge is read-only and manual.
Do not register automatic executors until selective automation is approved
through a separate, documented research and acceptance process.

Central safety flag: ALS_WRITING_ENABLED = False
Any attempt to register an automatic executor while writing is disabled
will raise a clear error at registration time, not at execution time.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from alscan.merge.operation import MergeOperation, ExecutionMode, SupportClassification

# ── Central safety flag ─────────────────────────────────────────────

ALS_WRITING_ENABLED: bool = False
"""When False, automatic executors cannot be registered.

This flag gates ALL .als-writing capability. It is the single control
point for the entire automation subsystem. No executor, CLI flag, GUI
control, or manifest setting may bypass this flag.

Set to True ONLY after:
1. A documented research plan is approved.
2. The target operation type passes a real-Ableton acceptance test.
3. Preflight, apply, validate, and rollback are all implemented.
4. Source-file immutability is re-verified.
5. The change is reviewed and explicitly approved.
"""


class ExecutorSupport(Enum):
    FULLY_SUPPORTED = "fully_supported"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


@dataclass
class SupportResult:
    supported: bool = False
    classification: ExecutorSupport = ExecutorSupport.UNSUPPORTED
    reasons: list[str] = field(default_factory=list)
    requires_strong_lineage: bool = True
    requires_supported_version: bool = True
    modifies_xml: bool = False
    copies_opaque_subtree: bool = False


@dataclass
class PreflightResult:
    ready: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    estimated_output_size: int = 0


@dataclass
class ApplyResult:
    success: bool = False
    output_path: str = ""
    operation_log: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bytes_written: int = 0
    temp_path: str = ""


@dataclass
class RiskDescription:
    risk_level: str = "low"
    description: str = ""
    can_undo: bool = True
    backup_recommended: bool = True
    worst_case: str = ""
    mitigation: str = ""


class OperationExecutor(ABC):
    @abstractmethod
    def supports(self, operation: MergeOperation, context: dict) -> SupportResult:
        ...

    @abstractmethod
    def supported_live_versions(self) -> list[str]:
        ...

    @abstractmethod
    def supported_operation_types(self) -> list[str]:
        ...

    @abstractmethod
    def confidence_requirements(self) -> str:
        ...

    @abstractmethod
    def lineage_requirements(self) -> str:
        ...

    @abstractmethod
    def modifies_xml(self) -> bool:
        ...

    @abstractmethod
    def copies_opaque_subtree(self) -> bool:
        ...

    @abstractmethod
    def validation_guarantees(self) -> list[str]:
        ...

    @abstractmethod
    def describe_risk(self, operation: MergeOperation) -> RiskDescription:
        ...

    def preflight(self, operation: MergeOperation, context: dict) -> PreflightResult:
        return PreflightResult(ready=True)

    def apply(
        self,
        operation: MergeOperation,
        source_tree: Any,
        destination_tree: Any,
    ) -> ApplyResult:
        return ApplyResult(
            success=False,
            errors=["apply() is not implemented for this executor."],
            warnings=["Only ManualInstructionExecutor and future specialized executors support automatic application."],
        )

    def validate(self, operation: MergeOperation, output_tree: Any) -> SupportResult:
        return self.supports(operation, {})


class ManualInstructionExecutor(OperationExecutor):
    def supports(self, operation: MergeOperation, context: dict) -> SupportResult:
        return SupportResult(
            supported=True,
            classification=ExecutorSupport.FULLY_SUPPORTED,
            reasons=["All operations are supported in manual mode."],
            requires_strong_lineage=False,
            requires_supported_version=False,
            modifies_xml=False,
            copies_opaque_subtree=False,
        )

    def supported_live_versions(self) -> list[str]:
        return ["any"]

    def supported_operation_types(self) -> list[str]:
        return ["all"]

    def confidence_requirements(self) -> str:
        return "none"

    def lineage_requirements(self) -> str:
        return "none"

    def modifies_xml(self) -> bool:
        return False

    def copies_opaque_subtree(self) -> bool:
        return False

    def validation_guarantees(self) -> list[str]:
        return ["Manual operations require user confirmation of completion."]

    def describe_risk(self, operation: MergeOperation) -> RiskDescription:
        return RiskDescription(
            risk_level="low",
            description="Manual operation — you perform the change in Ableton Live yourself.",
            can_undo=True,
            backup_recommended=True,
            worst_case="Manual error in Ableton Live.",
            mitigation="ALScan verifies the result after you complete the operation.",
        )


class VerificationOnlyExecutor(OperationExecutor):
    def supports(self, operation: MergeOperation, context: dict) -> SupportResult:
        return SupportResult(
            supported=True,
            classification=ExecutorSupport.FULLY_SUPPORTED,
            reasons=["Verification-only operations do not modify any file."],
            requires_strong_lineage=False,
            requires_supported_version=False,
            modifies_xml=False,
            copies_opaque_subtree=False,
        )

    def supported_live_versions(self) -> list[str]:
        return ["any"]

    def supported_operation_types(self) -> list[str]:
        return ["verification"]

    def confidence_requirements(self) -> str:
        return "none"

    def lineage_requirements(self) -> str:
        return "none"

    def modifies_xml(self) -> bool:
        return False

    def copies_opaque_subtree(self) -> bool:
        return False

    def validation_guarantees(self) -> list[str]:
        return [
            "Verification compares destination snapshot against expected values.",
            "Structural fingerprint comparison.",
        ]

    def describe_risk(self, operation: MergeOperation) -> RiskDescription:
        return RiskDescription(
            risk_level="low",
            description="Read-only verification — no file is modified.",
            can_undo=True,
            backup_recommended=False,
            worst_case="Verification failure indicates a manual step was missed.",
            mitigation="Re-run the missed manual step and verify again.",
        )


class ExecutorRegistry:
    def __init__(self):
        self._executors: dict[str, OperationExecutor] = {}
        self.register("manual", ManualInstructionExecutor())
        self.register("verification", VerificationOnlyExecutor())

    def register(self, name: str, executor: OperationExecutor) -> None:
        if not ALS_WRITING_ENABLED and not isinstance(
            executor, (ManualInstructionExecutor, VerificationOnlyExecutor)
        ):
            raise RuntimeError(
                f"Cannot register executor '{name}': ALS_WRITING_ENABLED is False. "
                f"Guided Merge is read-only and manual. Automatic .als writing is "
                f"not yet approved."
            )
        self._executors[name] = executor

    def get(self, name: str) -> OperationExecutor | None:
        return self._executors.get(name)

    def list_executors(self) -> list[str]:
        return list(self._executors.keys())

    def find_executor(self, operation: MergeOperation) -> OperationExecutor:
        candidates = []
        for executor in self._executors.values():
            if executor.supports(operation, {}).supported:
                candidates.append(executor)
        for executor in candidates:
            if executor is not self._executors.get("manual"):
                return executor
        return self._executors.get("manual", ManualInstructionExecutor())


_registry: ExecutorRegistry | None = None


def get_executor_registry() -> ExecutorRegistry:
    global _registry
    if _registry is None:
        _registry = ExecutorRegistry()
    return _registry

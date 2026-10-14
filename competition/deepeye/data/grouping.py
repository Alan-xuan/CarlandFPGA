"""C01 split-assignment validation for DeepEye datasets.

Part of the C01 "causal data and model input" foundation (owner C).  This
module validates caller-supplied split tables so that every complete parent
group (a FORCE well, a complete sim_em_v2 run/scenario, a sensor acquisition
batch) and every derivative/augmentation row stays in exactly one of the
train/validation/test splits inside each source domain.

Boundaries: dependency-free (Python standard library only).  It never
downloads, reads, hashes or fabricates licensed data and it records no data
claims; the caller supplies rows and this module only checks the assignment
table they describe.  Licensing, FORCE file identity and measured hashes are
C01 integration concerns handled outside this validator.

Row contract (a mapping, or an object with matching attributes):

* row_id        - non-empty string, unique within the table.
* source_domain - non-empty string; grouping is per domain, so the same
                  parent identity may exist independently in two domains.
* root_id       - non-empty string; identity of the complete parent group
                  (well id / complete run id / complete scenario id).
* split         - one of train / validation / test.
* derived_from  - optional row id this row is derived from or an augmentation
                  of; derivative chains must stay inside one root group and
                  one domain.

Violation codes: missing_identity, missing_split, invalid_split,
duplicate_row_id, cross_split_root, derivative_root_mismatch,
derivative_domain_mismatch, unknown_parent, derivative_cycle.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "SPLITS",
    "Violation",
    "SplitAssignmentError",
    "DomainSummary",
    "SplitValidationReport",
    "validate_split_assignments",
]

SPLITS: tuple[str, str, str] = ("train", "validation", "test")


@dataclass(frozen=True)
class Violation:
    """One rejected grouping rule occurrence."""

    code: str
    row_id: str | None
    detail: str


class SplitAssignmentError(ValueError):
    """Raised when a split-assignment table violates the grouping rules.

    ``violations`` carries every detected Violation in deterministic input
    order so callers can print all problems at once; the exception message
    summarises the codes.
    """

    def __init__(self, violations: Iterable[Violation]):
        self.violations: tuple[Violation, ...] = tuple(violations)
        codes = ", ".join(
            f"{item.code}({item.row_id or '-'})" for item in self.violations
        )
        super().__init__(
            f"split assignment rejected with {len(self.violations)} violation(s): {codes}"
        )


@dataclass(frozen=True)
class DomainSummary:
    """Accepted rows of one source domain, grouped by parent root."""

    source_domain: str
    rows: int
    roots: int
    derivatives: int
    split_rows: dict[str, int]
    root_splits: dict[str, str]


@dataclass(frozen=True)
class SplitValidationReport:
    """Deterministic summary of an accepted split assignment."""

    rows: int
    root_count: int
    split_rows: dict[str, int]
    domains: dict[str, DomainSummary]


def _read_field(row: object, name: str, default: object = None) -> object:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _is_identity(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def validate_split_assignments(
    rows: Iterable[object],
    *,
    splits: Sequence[str] = SPLITS,
) -> SplitValidationReport:
    """Validate a split-assignment table and return a deterministic report.

    ``rows`` items follow the row contract in the module docstring; mappings
    and attribute objects are both accepted.  Any rule break raises
    :class:`SplitAssignmentError` carrying every violation, so one call
    reports all problems instead of stopping at the first.

    On success the returned :class:`SplitValidationReport` records, per
    source domain, the accepted row count, root count, derivative count and
    the single split of every parent group; downstream code can therefore
    assert "no root crosses splits" before any dataset is materialised.
    """
    allowed = tuple(splits)
    if (
        not allowed
        or any(not isinstance(value, str) or not value for value in allowed)
        or len(set(allowed)) != len(allowed)
    ):
        raise ValueError("splits must be unique non-empty strings")

    violations: list[Violation] = []
    entries: list[dict[str, object]] = []
    seen_row_ids: set[str] = set()

    for index, row in enumerate(rows):
        row_id = _read_field(row, "row_id")
        source_domain = _read_field(row, "source_domain")
        root_id = _read_field(row, "root_id")
        split = _read_field(row, "split")
        derived_from = _read_field(row, "derived_from")

        label = row_id if _is_identity(row_id) else None
        broken = False
        for field_name, value in (
            ("row_id", row_id),
            ("source_domain", source_domain),
            ("root_id", root_id),
        ):
            if not _is_identity(value):
                violations.append(
                    Violation(
                        "missing_identity",
                        label,
                        f"row {index}: {field_name} must be a non-empty string",
                    )
                )
                broken = True
        if split is None or (isinstance(split, str) and not split):
            violations.append(
                Violation("missing_split", label, f"row {index}: split is required")
            )
            broken = True
        elif split not in allowed:
            violations.append(
                Violation(
                    "invalid_split",
                    label,
                    f"row {index}: split {split!r} is not one of {allowed}",
                )
            )
            broken = True
        if derived_from is not None and not _is_identity(derived_from):
            violations.append(
                Violation(
                    "missing_identity",
                    label,
                    f"row {index}: derived_from must be a non-empty string when present",
                )
            )
            broken = True
        if _is_identity(row_id):
            if row_id in seen_row_ids:
                violations.append(
                    Violation(
                        "duplicate_row_id",
                        row_id,
                        f"row {index}: row_id {row_id!r} is duplicated",
                    )
                )
                broken = True
            else:
                seen_row_ids.add(row_id)
        if broken:
            continue
        entries.append(
            {
                "row_id": row_id,
                "source_domain": source_domain,
                "root_id": root_id,
                "split": split,
                "derived_from": derived_from,
            }
        )

    by_row_id: dict[str, dict[str, object]] = {str(entry["row_id"]): entry for entry in entries}
    root_anchor: dict[tuple[str, str], str] = {}
    root_split: dict[tuple[str, str], str] = {}
    for entry in entries:
        key = (str(entry["source_domain"]), str(entry["root_id"]))
        established = root_split.get(key)
        if established is None:
            root_split[key] = str(entry["split"])
            root_anchor[key] = str(entry["row_id"])
        elif established != entry["split"]:
            violations.append(
                Violation(
                    "cross_split_root",
                    str(entry["row_id"]),
                    f"root {entry['root_id']!r} in domain {entry['source_domain']!r} "
                    f"is already assigned to {established!r} by row "
                    f"{root_anchor[key]!r}; row {entry['row_id']!r} uses "
                    f"{entry['split']!r}",
                )
            )

    for entry in entries:
        parent_id = entry["derived_from"]
        if parent_id is None:
            continue
        parent = by_row_id.get(str(parent_id))
        if parent is None:
            violations.append(
                Violation(
                    "unknown_parent",
                    str(entry["row_id"]),
                    f"derived_from {parent_id!r} is not present in the table",
                )
            )
            continue
        if parent["source_domain"] != entry["source_domain"]:
            violations.append(
                Violation(
                    "derivative_domain_mismatch",
                    str(entry["row_id"]),
                    f"parent {parent_id!r} is in domain {parent['source_domain']!r}, "
                    f"not {entry['source_domain']!r}",
                )
            )
            continue
        if parent["root_id"] != entry["root_id"]:
            violations.append(
                Violation(
                    "derivative_root_mismatch",
                    str(entry["row_id"]),
                    f"parent {parent_id!r} belongs to root {parent['root_id']!r}, "
                    f"not {entry['root_id']!r}",
                )
            )
            continue
        seen_chain = {str(entry["row_id"])}
        cursor: dict[str, object] | None = parent
        while cursor is not None:
            cursor_id = str(cursor["row_id"])
            if cursor_id in seen_chain:
                violations.append(
                    Violation(
                        "derivative_cycle",
                        str(entry["row_id"]),
                        f"derived_from chain of {entry['row_id']!r} revisits "
                        f"{cursor_id!r}",
                    )
                )
                break
            seen_chain.add(cursor_id)
            next_id = cursor["derived_from"]
            cursor = by_row_id.get(str(next_id)) if next_id is not None else None

    if violations:
        raise SplitAssignmentError(violations)

    domain_state: dict[str, dict[str, object]] = {}
    split_rows: dict[str, int] = {name: 0 for name in allowed}
    for entry in entries:
        domain = str(entry["source_domain"])
        state = domain_state.setdefault(
            domain,
            {
                "rows": 0,
                "derivatives": 0,
                "split_rows": {name: 0 for name in allowed},
                "root_splits": {},
            },
        )
        state["rows"] = int(state["rows"]) + 1
        if entry["derived_from"] is not None:
            state["derivatives"] = int(state["derivatives"]) + 1
        domain_split_rows = state["split_rows"]
        split_name = str(entry["split"])
        domain_split_rows[split_name] = domain_split_rows[split_name] + 1
        split_rows[split_name] += 1
        domain_root_splits = state["root_splits"]
        domain_root_splits[str(entry["root_id"])] = split_name

    domains: dict[str, DomainSummary] = {}
    for domain, state in domain_state.items():
        domains[domain] = DomainSummary(
            source_domain=domain,
            rows=int(state["rows"]),
            roots=len(state["root_splits"]),
            derivatives=int(state["derivatives"]),
            split_rows=dict(state["split_rows"]),
            root_splits=dict(state["root_splits"]),
        )

    return SplitValidationReport(
        rows=len(entries),
        root_count=len(root_split),
        split_rows=split_rows,
        domains=domains,
    )

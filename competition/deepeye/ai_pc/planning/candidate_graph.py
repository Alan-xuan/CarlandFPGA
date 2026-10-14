"""Exact normalized candidate cost and deterministic bounded small-graph search.

Frozen scope (taskbook_final.md G04 first software step)
--------------------------------------------------------
This module is the pure mathematical foundation for the book's first
small-graph exhaustive cost check.  The frozen candidate objective is

    J = 1.0 * normalized_length + 0.5 * time + 4.0 * cumulative_risk
        + 0.5 * curvature + 1.0 * uncertainty

and it is evaluated here with exact rational arithmetic only
(``fractions.Fraction``).  A bounded deterministic Dijkstra search finds the
minimum-J candidate path in a small abstract directed graph under the tie key

    (exact total cost, fewest edges, lexicographically smallest edge-id sequence)

independent of node and edge insertion order.

Authority boundaries
--------------------
- Pure mathematics: explicit inputs, explicit outputs, no clocks, no threads,
  no network, no files, no scene/truth/oracle/ML access, no mutable state.
- Every input graph in this job is a ``software_fixture``; any other
  ``source_domain`` is refused.  The five components are already normalized by
  an explicit software-fixture policy: production normalization scales and risk
  calibration are NOT frozen here and are never fitted, defaulted or invented.
- There is no geometry, collision, swept-volume, execution or wire field, and
  no orientation-aware motion primitive.  This API cannot authorize motion,
  cannot declare that a drill has reached a gate and establishes no physical
  feasibility.  Product G04/C04 and every hardware/system card remain not_run.
- Returned paths exist only inside the abstract input graph.

Deterministic search contract
-----------------------------
- ``CandidateGraph.search(start, goal, max_expansions)``; ``max_expansions`` is
  an exact non-bool integer in 0..64 (``MAX_EXPANSIONS``) that bounds the number
  of node expansions.
- A node is *expanded* (settled) when its best candidate is popped as the heap
  minimum and its outgoing edges are relaxed; every node is expanded at most
  once, therefore ``expansion_count <= node count``.  The goal is reported as
  soon as its best candidate is popped as the heap minimum and is not itself
  expanded.  If ``start == goal`` the result is immediately ``found`` with an
  empty edge path, exact cost 0 and zero expansions.
- If the expansion budget prevents settling a genuinely pending candidate the
  status is ``budget_exhausted`` and the partial frontier is never reported as
  a found path.  When the heap is fully exhausted without reaching the goal the
  status is ``unreachable``.
- Labels are compared by the exact rational weighted total first, then hop
  count, then the edge-id sequence; extending any path strictly increases its
  label key, so zero-cost cycles can never improve a candidate (they only add
  hops).
"""

from dataclasses import dataclass
from fractions import Fraction
from heapq import heappop, heappush
import math

__all__ = [
    "COMPONENT_NAMES",
    "COMPONENT_WEIGHTS",
    "MAX_NODES",
    "MAX_EDGES",
    "MAX_EXPANSIONS",
    "SOURCE_DOMAIN",
    "CandidateGraphError",
    "NormalizedCost",
    "Edge",
    "CandidateGraph",
    "SearchResult",
    "search_minimum_cost_path",
]

COMPONENT_NAMES = ("length", "time", "cumulative_risk", "curvature", "uncertainty")
COMPONENT_WEIGHTS = (Fraction(1), Fraction(1, 2), Fraction(4), Fraction(1, 2), Fraction(1))
MAX_NODES = 64
MAX_EDGES = 512
MAX_EXPANSIONS = 64
SOURCE_DOMAIN = "software_fixture"

_SEARCH_STATUSES = ("found", "unreachable", "budget_exhausted")


class CandidateGraphError(ValueError):
    """Deterministic rejection of malformed cost, edge, graph or search input."""


def _require_identifier(field, value):
    if type(value) is not str or not value:
        raise CandidateGraphError(
            "{} must be a nonempty str, got {!r}".format(field, value)
        )
    return value


def _exact_nonnegative_fraction(field, value):
    """Exact Fraction for int/finite-float/Fraction, else deterministic reject.

    A float is converted to its exact binary rational (``Fraction(value)``),
    never through a rounded string.  bool is rejected before the int check and
    NaN/Inf are rejected before conversion.
    """

    if type(value) is bool or type(value) not in (int, float, Fraction):
        raise CandidateGraphError(
            "{} must be int, finite float or Fraction, got {}".format(
                field, type(value).__name__
            )
        )
    if type(value) is float:
        if not math.isfinite(value):
            raise CandidateGraphError("{} must be finite, got {!r}".format(field, value))
        fraction = Fraction(value)
    else:
        fraction = Fraction(value)
    if fraction < 0:
        raise CandidateGraphError(
            "{} must be nonnegative, got {}".format(field, fraction)
        )
    return fraction


def _copy_sequence(field, value):
    if type(value) is not list and type(value) is not tuple:
        raise CandidateGraphError(
            "{} must be a list or tuple, got {}".format(field, type(value).__name__)
        )
    return tuple(value)

@dataclass(frozen=True, init=False)
class NormalizedCost:
    """Five exact nonnegative normalized components in fixed order.

    Order: length, time, cumulative_risk, curvature, uncertainty.  Public
    construction accepts exact ``int``, finite ``float`` (stored as its exact
    binary rational) or ``fractions.Fraction`` copies and rejects bool,
    negative, NaN, infinite and unsupported values.  The component weights are
    fixed to (1, 1/2, 4, 1/2, 1); there is no caller weight override, no
    rounding, no float overflow rule and no epsilon tie rule.  There is no
    production normalization, scale fitting or risk calibration here: callers
    must pass components already normalized by an explicit software-fixture
    policy.
    """

    length: Fraction
    time: Fraction
    cumulative_risk: Fraction
    curvature: Fraction
    uncertainty: Fraction

    def __init__(self, length, time, cumulative_risk, curvature, uncertainty):
        values = (length, time, cumulative_risk, curvature, uncertainty)
        for name, value in zip(COMPONENT_NAMES, values):
            object.__setattr__(self, name, _exact_nonnegative_fraction(name, value))

    def components(self):
        """The five exact components as an immutable tuple in fixed order."""

        return (self.length, self.time, self.cumulative_risk, self.curvature, self.uncertainty)

    @property
    def weighted_total(self):
        """Exact rational J = 1*length + 1/2*time + 4*risk + 1/2*curvature + 1*uncertainty."""

        total = Fraction(0)
        for weight, component in zip(COMPONENT_WEIGHTS, self.components()):
            total = total + weight * component
        return total


@dataclass(frozen=True)
class Edge:
    """Immutable directed edge between two declared abstract graph nodes.

    ``edge_id``, ``source`` and ``target`` are nonempty strings and ``cost`` is
    a ``NormalizedCost``; nothing mutable is retained.
    """

    edge_id: str
    source: str
    target: str
    cost: NormalizedCost

    def __post_init__(self):
        _require_identifier("edge_id", self.edge_id)
        _require_identifier("source", self.source)
        _require_identifier("target", self.target)
        if type(self.cost) is not NormalizedCost:
            raise CandidateGraphError(
                "cost must be a NormalizedCost, got {}".format(type(self.cost).__name__)
            )

@dataclass(frozen=True, init=False)
class SearchResult:
    """Immutable search outcome; it grants no motion or execution authority.

    ``status`` is one of "found", "unreachable" or "budget_exhausted".
    ``edge_ids``/``node_ids`` are immutable tuples; they are empty unless the
    status is found, in which case ``node_ids[i+1]`` is the target of
    ``edge_ids[i]``.  ``cost`` is the exact rational weighted total when found
    and None otherwise.  ``expansion_count`` is the number of expanded
    (settled) nodes before the returned status, which is at most the node
    count.  There is no action-authorization field.
    """

    status: str
    edge_ids: tuple
    node_ids: tuple
    cost: object
    expansion_count: int

    def __init__(self, status, edge_ids, node_ids, cost, expansion_count):
        if status not in _SEARCH_STATUSES:
            raise CandidateGraphError(
                "status must be one of {}, got {!r}".format(_SEARCH_STATUSES, status)
            )
        edge_tuple = _copy_sequence("edge_ids", edge_ids)
        node_tuple = _copy_sequence("node_ids", node_ids)
        for entry in edge_tuple:
            _require_identifier("edge_ids entry", entry)
        for entry in node_tuple:
            _require_identifier("node_ids entry", entry)
        if type(expansion_count) is not int or expansion_count < 0:
            raise CandidateGraphError(
                "expansion_count must be a nonnegative exact int, got {!r}".format(
                    expansion_count
                )
            )
        if status == "found":
            if type(cost) is not Fraction or cost < 0:
                raise CandidateGraphError(
                    "found results require an exact nonnegative Fraction cost"
                )
            if len(node_tuple) != len(edge_tuple) + 1:
                raise CandidateGraphError(
                    "found results require len(node_ids) == len(edge_ids) + 1"
                )
        else:
            if cost is not None:
                raise CandidateGraphError(
                    "cost is reported only for found results"
                )
            if edge_tuple or node_tuple:
                raise CandidateGraphError(
                    "{} results carry empty edge_ids/node_ids".format(status)
                )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "edge_ids", edge_tuple)
        object.__setattr__(self, "node_ids", node_tuple)
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "expansion_count", expansion_count)

@dataclass(frozen=True, init=False)
class CandidateGraph:
    """Immutable small directed graph of software-fixture candidates.

    At most ``MAX_NODES`` (64) nodes and ``MAX_EDGES`` (512) edges.  Node ids
    and edge ids are unique nonempty strings; every edge endpoint must name a
    declared node; duplicate nodes, duplicate edge ids and unknown endpoints
    are rejected up front even if they would be unreachable.  Parallel distinct
    edges, self loops and cycles are allowed; all costs are nonnegative.  The
    caller's node and edge lists are copied into tuples, so later mutation of
    those lists cannot alter the graph.  Only ``source_domain`` exactly equal to
    "software_fixture" is accepted: this graph is abstract, carries no geometry,
    collision or execution meaning and cannot authorize motion.
    """

    source_domain: str
    _node_ids: tuple
    _edges: tuple

    def __init__(self, node_ids, edges, source_domain=SOURCE_DOMAIN):
        if type(source_domain) is not str or source_domain != SOURCE_DOMAIN:
            raise CandidateGraphError(
                "source_domain must be exactly {!r}; only software fixtures are accepted".format(
                    SOURCE_DOMAIN
                )
            )
        node_tuple = _copy_sequence("node_ids", node_ids)
        edge_tuple = _copy_sequence("edges", edges)
        if len(node_tuple) > MAX_NODES:
            raise CandidateGraphError(
                "at most {} nodes are allowed, got {}".format(MAX_NODES, len(node_tuple))
            )
        if len(edge_tuple) > MAX_EDGES:
            raise CandidateGraphError(
                "at most {} edges are allowed, got {}".format(MAX_EDGES, len(edge_tuple))
            )
        declared = set()
        for node in node_tuple:
            _require_identifier("node_ids entry", node)
            if node in declared:
                raise CandidateGraphError("duplicate node id {!r}".format(node))
            declared.add(node)
        seen_edges = set()
        for edge in edge_tuple:
            if type(edge) is not Edge:
                raise CandidateGraphError(
                    "edges entries must be Edge instances, got {}".format(
                        type(edge).__name__
                    )
                )
            if edge.edge_id in seen_edges:
                raise CandidateGraphError("duplicate edge id {!r}".format(edge.edge_id))
            seen_edges.add(edge.edge_id)
            if edge.source not in declared:
                raise CandidateGraphError(
                    "edge {!r} source {!r} is not a declared node".format(
                        edge.edge_id, edge.source
                    )
                )
            if edge.target not in declared:
                raise CandidateGraphError(
                    "edge {!r} target {!r} is not a declared node".format(
                        edge.edge_id, edge.target
                    )
                )
        object.__setattr__(self, "source_domain", SOURCE_DOMAIN)
        object.__setattr__(self, "_node_ids", node_tuple)
        object.__setattr__(self, "_edges", edge_tuple)

    @property
    def node_ids(self):
        """Declared node ids in the caller's order, as an immutable tuple."""

        return self._node_ids

    @property
    def edges(self):
        """Edges in the caller's order, as an immutable tuple."""

        return self._edges

    @property
    def node_count(self):
        return len(self._node_ids)

    @property
    def edge_count(self):
        return len(self._edges)
    def search(self, start, goal, max_expansions):
        """Bounded deterministic minimum-J search in this abstract graph.

        ``start`` and ``goal`` must be declared node ids.  ``max_expansions``
        must be an exact non-bool int in 0..MAX_EXPANSIONS.  Returns an
        immutable ``SearchResult``:

        - "found": the goal's optimal candidate was popped; ``edge_ids`` /
          ``node_ids`` describe the minimum -(cost, edges, edge-id sequence)
          path and ``cost`` is its exact rational weighted total.  ``start``
          equal to ``goal`` returns found with cost 0 and no expansion.
        - "budget_exhausted": the expansion budget stopped a genuinely pending
          candidate before the goal could be certified; no partial path is
          reported.
        - "unreachable": the frontier was fully exhausted and no path exists.

        Every node is expanded at most once, so ``expansion_count`` never
        exceeds the node count.  The result carries no motion, collision or
        execution authority.
        """

        _require_identifier("start", start)
        _require_identifier("goal", goal)
        if start not in self._node_ids:
            raise CandidateGraphError(
                "start {!r} is not a declared node".format(start)
            )
        if goal not in self._node_ids:
            raise CandidateGraphError(
                "goal {!r} is not a declared node".format(goal)
            )
        if type(max_expansions) is not int:
            raise CandidateGraphError(
                "max_expansions must be an exact int, got {}".format(
                    type(max_expansions).__name__
                )
            )
        if max_expansions < 0 or max_expansions > MAX_EXPANSIONS:
            raise CandidateGraphError(
                "max_expansions must be in 0..{}, got {}".format(
                    MAX_EXPANSIONS, max_expansions
                )
            )
        if start == goal:
            return SearchResult(
                status="found",
                edge_ids=(),
                node_ids=(start,),
                cost=Fraction(0),
                expansion_count=0,
            )
        edges_by_id = {}
        outgoing = {}
        for edge in self._edges:
            edges_by_id[edge.edge_id] = edge
            outgoing.setdefault(edge.source, []).append(edge)
        for source in outgoing:
            outgoing[source] = tuple(sorted(outgoing[source], key=lambda item: item.edge_id))
        best = {start: (Fraction(0), 0, ())}
        heap = [(Fraction(0), 0, (), start)]
        settled = set()
        expansions = 0
        while heap:
            cost, hops, sequence, node = heappop(heap)
            if node in settled:
                continue
            if best.get(node) != (cost, hops, sequence):
                continue
            if node == goal:
                return SearchResult(
                    status="found",
                    edge_ids=sequence,
                    node_ids=_node_chain(start, sequence, edges_by_id),
                    cost=cost,
                    expansion_count=expansions,
                )
            if expansions >= max_expansions:
                return SearchResult(
                    status="budget_exhausted",
                    edge_ids=(),
                    node_ids=(),
                    cost=None,
                    expansion_count=expansions,
                )
            settled.add(node)
            expansions += 1
            for edge in outgoing.get(node, ()):
                target = edge.target
                if target in settled:
                    continue
                candidate = (
                    cost + edge.cost.weighted_total,
                    hops + 1,
                    sequence + (edge.edge_id,),
                )
                if target not in best or candidate < best[target]:
                    best[target] = candidate
                    heappush(heap, (candidate[0], candidate[1], candidate[2], target))
        return SearchResult(
            status="unreachable",
            edge_ids=(),
            node_ids=(),
            cost=None,
            expansion_count=expansions,
        )


def search_minimum_cost_path(graph, start, goal, max_expansions):
    """Pure functional entry point; see ``CandidateGraph.search``."""

    if type(graph) is not CandidateGraph:
        raise CandidateGraphError(
            "graph must be a CandidateGraph, got {}".format(type(graph).__name__)
        )
    return graph.search(start, goal, max_expansions)


def _node_chain(start, edge_sequence, edges_by_id):
    nodes = [start]
    for edge_id in edge_sequence:
        nodes.append(edges_by_id[edge_id].target)
    return tuple(nodes)
"""Exhaustive small-graph verification for ai_pc/planning/candidate_graph.py.

Software-only evidence for the frozen G04 first mathematical step.

- 100 fixed-seed small directed software-fixture graphs (2..7 nodes) are
  compared against an independent brute-force enumeration of all simple paths
  using hand-coded exact rational arithmetic for the frozen objective
  J = 1*length + 1/2*time + 4*cumulative_risk + 1/2*curvature + 1*uncertainty.
  The solver's own cost method is never used to derive expectations.
- Seeded graphs include integer/rational/exact-float/zero costs, parallel
  distinct edges, self loops, cycles and unreachable pairs; every ordered node
  pair of every graph is checked, plus the start==goal rule.
- Insertion-order permutations, tie cases (equal cost fewer hops, equal cost
  lexicographic edge-id ties), zero-cost cycles, lower-cost-more-hops, caller
  list mutation, limits/bounds, malformed inputs and budget truncation
  (including budget 0 and budget_exhausted) are covered explicitly.
- 3D coordinates appear ONLY as synthetic fixture metadata used to derive
  distance-style costs; this certifies no geometry, curvature, orientation,
  collision or braking property.

These tests are not a planner acceptance, not G04/C04 and not any product or
hardware card.  The suite is portable from an ordinary checkout: it reads only
the candidate_graph.py module next to this checkout and uses no private files,
no dataset archive and no external packages.
"""

import dataclasses
import decimal
import importlib.util
import math
import random
import sys
import unittest
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True

_HERE = Path(__file__).resolve().parent
_MODULE_PATH = _HERE.parents[2] / "ai_pc" / "planning" / "candidate_graph.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("deepeye_candidate_graph", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


candidate_graph = _load_module()

NormalizedCost = candidate_graph.NormalizedCost
Edge = candidate_graph.Edge
CandidateGraph = candidate_graph.CandidateGraph
CandidateGraphError = candidate_graph.CandidateGraphError
SearchResult = candidate_graph.SearchResult
search_minimum_cost_path = candidate_graph.search_minimum_cost_path
MAX_EXPANSIONS = candidate_graph.MAX_EXPANSIONS

GRAPH_SEED_BASE = 20261015
GRAPH_COUNT = 100


# ---------------------------------------------------------------------------
# Independent reference implementation (never uses the solver cost methods)
# ---------------------------------------------------------------------------

def reference_weighted(components):
    """Hand-coded exact J arithmetic; deliberately not the module's method."""

    length, time, risk, curvature, uncertainty = components
    total = length * 1
    total = total + time / 2
    total = total + risk * 4
    total = total + curvature / 2
    total = total + uncertainty * 1
    return total


def _components(rng):
    """Exact nonnegative components: zeros, integers, halves/thirds, exact floats."""

    mode = rng.randrange(5)
    if mode == 0:
        return (Fraction(0),) * 5
    if mode == 1:
        return tuple(Fraction(rng.randrange(0, 4)) for _ in range(5))
    if mode == 2:
        return tuple(
            Fraction(rng.randrange(0, 7), rng.choice((2, 3, 4))) for _ in range(5)
        )
    if mode == 3:
        base = Fraction(rng.randrange(0, 5), 2)
        return (base, Fraction(0), base / 2, Fraction(0), Fraction(rng.randrange(0, 3)))
    value = rng.choice((0.0, 0.5, 0.25, 0.125, 1.0))
    return (Fraction(value),) * 5


def build_graph_fixture(seed):
    """Deterministic software-fixture graph description for one seed."""

    rng = random.Random(seed)
    node_count = rng.randint(2, 7)
    node_ids = tuple("n%d" % index for index in range(node_count))
    edges = []
    for _ in range(rng.randint(0, 10)):
        edges.append(
            {
                "edge_id": "e%02d" % len(edges),
                "source": rng.choice(node_ids),
                "target": rng.choice(node_ids),
                "components": _components(rng),
            }
        )
    if edges and rng.random() < 0.6:
        base = rng.choice(edges)
        components = base["components"] if rng.random() < 0.5 else _components(rng)
        edges.append(
            {
                "edge_id": "p%02d" % len(edges),
                "source": base["source"],
                "target": base["target"],
                "components": components,
            }
        )
    if rng.random() < 0.35:
        node = rng.choice(node_ids)
        edges.append(
            {
                "edge_id": "z%02d" % len(edges),
                "source": node,
                "target": node,
                "components": (Fraction(0),) * 5,
            }
        )
    if rng.random() < 0.35:
        first, second = rng.sample(node_ids, 2)
        edges.append(
            {
                "edge_id": "c%02d" % len(edges),
                "source": first,
                "target": second,
                "components": (Fraction(0),) * 5,
            }
        )
        edges.append(
            {
                "edge_id": "c%02d" % len(edges),
                "source": second,
                "target": first,
                "components": (Fraction(0),) * 5,
            }
        )
    return {"seed": seed, "node_ids": node_ids, "edges": tuple(edges)}

def enumerate_simple_paths(fixture, start, goal):
    """All simple (cycle-free) edge-id sequences from start to goal."""

    by_source = {}
    for edge in fixture["edges"]:
        by_source.setdefault(edge["source"], []).append(edge)
    results = []

    def walk(node, sequence, visited):
        if node == goal:
            results.append(sequence)
            return
        for edge in by_source.get(node, ()):
            if edge["target"] in visited:
                continue
            walk(edge["target"], sequence + (edge["edge_id"],), visited | {edge["target"]})

    walk(start, (), frozenset((start,)))
    return results


def reference_answer(fixture, start, goal):
    """Independent expected (cost, hops, edge_ids, node_ids); None when no path."""

    if start == goal:
        return (Fraction(0), 0, (), (start,))
    by_id = {edge["edge_id"]: edge for edge in fixture["edges"]}
    best_key = None
    best_chain = None
    for sequence in enumerate_simple_paths(fixture, start, goal):
        total = Fraction(0)
        chain = [start]
        for edge_id in sequence:
            edge = by_id[edge_id]
            total = total + reference_weighted(edge["components"])
            chain.append(edge["target"])
        key = (total, len(sequence), sequence)
        if best_key is None or key < best_key:
            best_key = key
            best_chain = tuple(chain)
    if best_key is None:
        return None
    return (best_key[0], best_key[1], best_key[2], best_chain)


def reference_reachable_count(fixture, start):
    """Independent node-reachability count under any nonempty walk."""

    by_source = {}
    for edge in fixture["edges"]:
        by_source.setdefault(edge["source"], []).append(edge["target"])
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for target in by_source.get(node, ()):
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return len(seen)


def _has_directed_cycle(node_ids, edges):
    adjacency = {node: [] for node in node_ids}
    for edge in edges:
        adjacency[edge["source"]].append(edge["target"])
    state = {}

    def visit(node):
        state[node] = 1
        for target in adjacency[node]:
            if state.get(target) == 1:
                return True
            if state.get(target) is None and visit(target):
                return True
        state[node] = 2
        return False

    return any(state.get(node) is None and visit(node) for node in node_ids)


def build_graph(fixture, node_order=None, edge_order=None):
    node_ids = list(fixture["node_ids"]) if node_order is None else list(node_order)
    edges = list(fixture["edges"]) if edge_order is None else list(edge_order)
    return CandidateGraph(
        node_ids,
        [
            Edge(
                edge["edge_id"],
                edge["source"],
                edge["target"],
                NormalizedCost(*edge["components"]),
            )
            for edge in edges
        ],
    )


class NormalizedCostTests(unittest.TestCase):
    def test_exact_components_and_weighted_total(self):
        cost = NormalizedCost(1, 1, 1, 1, 1)
        self.assertEqual(cost.components(), (Fraction(1),) * 5)
        self.assertEqual(cost.weighted_total, Fraction(7))
        mixed = NormalizedCost(
            Fraction(1, 3), Fraction(2, 3), Fraction(0), Fraction(1, 7), Fraction(5, 2)
        )
        # hand-derived: 1/3 + (2/3)/2 + 0 + (1/7)/2 + 5/2 = 68/21
        self.assertEqual(mixed.weighted_total, Fraction(68, 21))
        self.assertIsInstance(mixed.weighted_total, Fraction)
        self.assertEqual(NormalizedCost(0, 0, 0, 0, 0).weighted_total, Fraction(0))

    def test_float_components_use_exact_binary_rational(self):
        cost = NormalizedCost(0.1, 0.0, 0.0, 0.0, 0.0)
        self.assertEqual(cost.length, Fraction(3602879701896397, 36028797018963968))
        self.assertEqual(cost.length, Fraction(0.1))
        self.assertNotEqual(cost.length, Fraction(1, 10))
        halves = NormalizedCost(0.5, 0.25, 0.125, 2.0, 0.0)
        self.assertEqual(
            halves.components(),
            (Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(2), Fraction(0)),
        )

    def test_rejects_bool_negative_nan_inf_and_unsupported(self):
        bad_values = (
            True,
            False,
            -1,
            Fraction(-1, 2),
            -0.5,
            float("nan"),
            float("inf"),
            float("-inf"),
            "1",
            None,
            decimal.Decimal("1"),
            object(),
        )
        for position in range(5):
            for bad in bad_values:
                values = [Fraction(0)] * 5
                values[position] = bad
                with self.subTest(position=position, bad=repr(bad)):
                    with self.assertRaises(CandidateGraphError):
                        NormalizedCost(*values)

    def test_no_weight_override_and_fixed_exports(self):
        with self.assertRaises(TypeError):
            NormalizedCost(1, 1, 1, 1, 1, weights=(1, 1, 1, 1, 1))
        self.assertEqual(
            candidate_graph.COMPONENT_WEIGHTS,
            (Fraction(1), Fraction(1, 2), Fraction(4), Fraction(1, 2), Fraction(1)),
        )
        self.assertEqual(
            candidate_graph.COMPONENT_NAMES,
            ("length", "time", "cumulative_risk", "curvature", "uncertainty"),
        )

    def test_immutable_instances(self):
        cost = NormalizedCost(1, 2, 3, 4, 5)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            cost.length = Fraction(9)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            cost.curvature = Fraction(0)

class EdgeAndGraphValidationTests(unittest.TestCase):
    def test_valid_graph_accepts_parallel_self_loops_and_cycles(self):
        node_ids = ["a", "b"]
        edges = [
            Edge("e1", "a", "b", NormalizedCost(1, 0, 0, 0, 0)),
            Edge("e2", "a", "b", NormalizedCost(0, 0, 0, 0, 0)),
            Edge("e3", "b", "b", NormalizedCost(0, 0, 0, 0, 0)),
            Edge("e4", "b", "a", NormalizedCost(0, 0, 0, 0, 0)),
        ]
        graph = CandidateGraph(node_ids, edges)
        self.assertEqual(graph.source_domain, "software_fixture")
        self.assertEqual(graph.node_ids, ("a", "b"))
        self.assertEqual(tuple(edge.edge_id for edge in graph.edges), ("e1", "e2", "e3", "e4"))
        self.assertEqual(graph.node_count, 2)
        self.assertEqual(graph.edge_count, 4)

    def test_node_validation(self):
        cost = NormalizedCost(0, 0, 0, 0, 0)
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", "a"], [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", ""], [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", 7], [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", True], [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph("ab", [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph({"a", "b"}, [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(None, [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph([], None)
        self.assertEqual(CandidateGraph([], []).node_count, 0)

    def test_edge_validation(self):
        cost = NormalizedCost(0, 0, 0, 0, 0)
        good = Edge("e1", "a", "b", cost)
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", "b"], [good, Edge("e1", "b", "a", cost)])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", "b"], [Edge("e2", "a", "missing", cost)])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", "b"], [Edge("e2", "missing", "b", cost)])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", "b"], [{"edge_id": "e2"}])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", "b"], [7])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(["a", "b"], "edges")
        with self.assertRaises(CandidateGraphError):
            Edge("", "a", "b", cost)
        with self.assertRaises(CandidateGraphError):
            Edge("e1", "", "b", cost)
        with self.assertRaises(CandidateGraphError):
            Edge("e1", "a", 7, cost)
        with self.assertRaises(CandidateGraphError):
            Edge("e1", "a", "b", 3)
        with self.assertRaises(CandidateGraphError):
            Edge("e1", "a", "b", None)

    def test_source_domain_must_be_software_fixture(self):
        cost = NormalizedCost(0, 0, 0, 0, 0)
        for domain in ("production", "sim", "sim_em_v2", "", None, True, 7):
            with self.subTest(domain=repr(domain)):
                with self.assertRaises(CandidateGraphError):
                    CandidateGraph(["a", "b"], [Edge("e1", "a", "b", cost)], domain)
        CandidateGraph(["a", "b"], [Edge("e1", "a", "b", cost)], "software_fixture")

    def test_bounds_64_nodes_and_512_edges(self):
        cost = NormalizedCost(0, 0, 0, 0, 0)
        nodes_64 = ["n%02d" % index for index in range(64)]
        edges_512 = [
            Edge("e%04d" % index, nodes_64[0], nodes_64[1], cost) for index in range(512)
        ]
        graph = CandidateGraph(nodes_64, edges_512)
        self.assertEqual(graph.node_count, 64)
        self.assertEqual(graph.edge_count, 512)
        nodes_65 = nodes_64 + ["n64"]
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(nodes_65, [])
        with self.assertRaises(CandidateGraphError):
            CandidateGraph(nodes_64, edges_512 + [Edge("extra", nodes_64[0], nodes_64[1], cost)])

    def test_caller_list_mutation_cannot_alter_graph(self):
        node_list = ["s", "m", "g"]
        edge_list = [
            Edge("e1", "s", "m", NormalizedCost(1, 0, 0, 0, 0)),
            Edge("e2", "m", "g", NormalizedCost(1, 0, 0, 0, 0)),
        ]
        graph = CandidateGraph(node_list, edge_list)
        before = graph.search("s", "g", MAX_EXPANSIONS)
        node_list.append("x")
        node_list[0] = "z"
        edge_list.pop()
        edge_list.append(Edge("e9", "s", "g", NormalizedCost(0, 0, 0, 0, 0)))
        after = graph.search("s", "g", MAX_EXPANSIONS)
        self.assertEqual(graph.node_ids, ("s", "m", "g"))
        self.assertEqual(tuple(edge.edge_id for edge in graph.edges), ("e1", "e2"))
        self.assertEqual(before, after)
        self.assertEqual(after.edge_ids, ("e1", "e2"))
        self.assertEqual(after.cost, Fraction(2))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            graph.source_domain = "production"


class SearchSemanticsTests(unittest.TestCase):
    def test_start_equal_goal_returns_found_empty_without_expansion(self):
        graph = CandidateGraph(["a"], [Edge("loop", "a", "a", NormalizedCost(0, 0, 0, 0, 0))])
        result = graph.search("a", "a", 0)
        self.assertEqual(result.status, "found")
        self.assertEqual(result.edge_ids, ())
        self.assertEqual(result.node_ids, ("a",))
        self.assertEqual(result.cost, Fraction(0))
        self.assertEqual(result.expansion_count, 0)

    def test_budget_zero_is_budget_exhausted_when_work_pending(self):
        graph = CandidateGraph(["s", "g"], [Edge("e1", "s", "g", NormalizedCost(1, 0, 0, 0, 0))])
        result = graph.search("s", "g", 0)
        self.assertEqual(result.status, "budget_exhausted")
        self.assertEqual(result.edge_ids, ())
        self.assertEqual(result.node_ids, ())
        self.assertIsNone(result.cost)
        self.assertEqual(result.expansion_count, 0)
        isolated = CandidateGraph(["s", "g"], [])
        self.assertEqual(isolated.search("s", "g", 0).status, "budget_exhausted")
        exhausted = isolated.search("s", "g", 1)
        self.assertEqual(exhausted.status, "unreachable")
        self.assertEqual(exhausted.expansion_count, 1)

    def test_budget_truncation_never_reports_partial_path(self):
        graph = CandidateGraph(
            ["s", "a", "g"],
            [
                Edge("e1", "s", "a", NormalizedCost(1, 0, 0, 0, 0)),
                Edge("e2", "a", "g", NormalizedCost(1, 0, 0, 0, 0)),
            ],
        )
        truncated = graph.search("s", "g", 1)
        self.assertEqual(truncated.status, "budget_exhausted")
        self.assertEqual(truncated.edge_ids, ())
        self.assertIsNone(truncated.cost)
        self.assertEqual(truncated.expansion_count, 1)
        found = graph.search("s", "g", 2)
        self.assertEqual(found.status, "found")
        self.assertEqual(found.edge_ids, ("e1", "e2"))
        self.assertEqual(found.cost, Fraction(2))
        self.assertEqual(found.expansion_count, 2)

    def test_search_input_validation(self):
        graph = CandidateGraph(["s", "g"], [])
        for bad_budget in (-1, MAX_EXPANSIONS + 1, 1.0, True, "2", None, Fraction(2)):
            with self.subTest(bad_budget=repr(bad_budget)):
                with self.assertRaises(CandidateGraphError):
                    graph.search("s", "g", bad_budget)
        for bad_id in ("", 7, None, "unknown"):
            with self.subTest(bad_id=repr(bad_id)):
                with self.assertRaises(CandidateGraphError):
                    graph.search(bad_id, "g", 1)
                with self.assertRaises(CandidateGraphError):
                    graph.search("s", bad_id, 1)
        with self.assertRaises(CandidateGraphError):
            search_minimum_cost_path("graph", "s", "g", 1)
        self.assertEqual(search_minimum_cost_path(graph, "s", "g", 1).status, "unreachable")

    def test_module_level_entry_matches_method(self):
        graph = CandidateGraph(["s", "g"], [Edge("e1", "s", "g", NormalizedCost(1, 0, 0, 0, 0))])
        self.assertEqual(search_minimum_cost_path(graph, "s", "g", 8), graph.search("s", "g", 8))

    def test_result_constructor_validation_and_immutability(self):
        with self.assertRaises(CandidateGraphError):
            SearchResult("done", (), (), None, 0)
        with self.assertRaises(CandidateGraphError):
            SearchResult("found", (), (), None, 0)
        with self.assertRaises(CandidateGraphError):
            SearchResult("found", (), ("s",), Fraction(0), -1)
        with self.assertRaises(CandidateGraphError):
            SearchResult("unreachable", ("e",), (), None, 0)
        with self.assertRaises(CandidateGraphError):
            SearchResult("budget_exhausted", (), (), Fraction(0), 0)
        ok = SearchResult("unreachable", (), (), None, 3)
        self.assertEqual(ok.expansion_count, 3)
        self.assertIsNone(ok.cost)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ok.status = "found"

class TieBreakTests(unittest.TestCase):
    def test_equal_cost_prefers_fewer_edges(self):
        graph = CandidateGraph(
            ["s", "m", "g"],
            [
                Edge("direct", "s", "g", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("leg1", "s", "m", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("leg2", "m", "g", NormalizedCost(0, 0, 0, 0, 0)),
            ],
        )
        result = graph.search("s", "g", MAX_EXPANSIONS)
        self.assertEqual(result.status, "found")
        self.assertEqual(result.edge_ids, ("direct",))
        self.assertEqual(result.cost, Fraction(0))

    def test_equal_cost_equal_hops_lexicographic_tie(self):
        graph = CandidateGraph(
            ["s", "g"],
            [
                Edge("eB", "s", "g", NormalizedCost(3, 0, 0, 0, 0)),
                Edge("eA", "s", "g", NormalizedCost(3, 0, 0, 0, 0)),
            ],
        )
        result = graph.search("s", "g", MAX_EXPANSIONS)
        self.assertEqual(result.edge_ids, ("eA",))
        self.assertEqual(result.cost, Fraction(3))

    def test_equal_cost_two_hop_lexicographic_tie(self):
        graph = CandidateGraph(
            ["s", "a", "b", "g"],
            [
                Edge("e1", "s", "a", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("e2", "s", "b", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("e3", "a", "g", NormalizedCost(1, 0, 0, 0, 0)),
                Edge("e4", "b", "g", NormalizedCost(1, 0, 0, 0, 0)),
            ],
        )
        result = graph.search("s", "g", MAX_EXPANSIONS)
        self.assertEqual(result.edge_ids, ("e1", "e3"))
        self.assertEqual(result.cost, Fraction(1))

    def test_lower_cost_more_hops_wins_by_cost(self):
        graph = CandidateGraph(
            ["s", "m", "g"],
            [
                Edge("direct", "s", "g", NormalizedCost(10, 0, 0, 0, 0)),
                Edge("leg1", "s", "m", NormalizedCost(1, 0, 0, 0, 0)),
                Edge("leg2", "m", "g", NormalizedCost(1, 0, 0, 0, 0)),
            ],
        )
        result = graph.search("s", "g", MAX_EXPANSIONS)
        self.assertEqual(result.edge_ids, ("leg1", "leg2"))
        self.assertEqual(result.cost, Fraction(2))

    def test_zero_cost_cycles_cannot_improve_via_more_hops(self):
        graph = CandidateGraph(
            ["s", "a", "g"],
            [
                Edge("e1", "s", "a", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("e2", "a", "s", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("e3", "a", "g", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("e4", "s", "g", NormalizedCost(0, 0, 0, 0, 0)),
            ],
        )
        result = graph.search("s", "g", MAX_EXPANSIONS)
        self.assertEqual(result.status, "found")
        self.assertEqual(result.edge_ids, ("e4",))
        self.assertEqual(result.cost, Fraction(0))
        cycle_only = CandidateGraph(
            ["s", "a", "g"],
            [
                Edge("c1", "s", "a", NormalizedCost(0, 0, 0, 0, 0)),
                Edge("c2", "a", "s", NormalizedCost(0, 0, 0, 0, 0)),
            ],
        )
        self.assertEqual(cycle_only.search("s", "g", MAX_EXPANSIONS).status, "unreachable")

    def test_float_costs_compare_exactly(self):
        graph = CandidateGraph(
            ["s", "m", "g"],
            [
                Edge("f1", "s", "m", NormalizedCost(0.5, 0, 0, 0, 0)),
                Edge("f2", "m", "g", NormalizedCost(0.1, 0, 0, 0, 0)),
                Edge("direct", "s", "g", NormalizedCost(0.6, 0, 0, 0, 0)),
            ],
        )
        result = graph.search("s", "g", MAX_EXPANSIONS)
        # exact binary rationals: 0.5 + 0.1 is slightly larger than float 0.6
        self.assertGreater(Fraction(0.5) + Fraction(0.1), Fraction(0.6))
        self.assertEqual(result.edge_ids, ("direct",))
        self.assertEqual(result.cost, Fraction(0.6))

    def test_synthetic_coordinate_metadata_only_generates_distance_costs(self):
        # Coordinates are ONLY synthetic fixture metadata used to derive
        # distance-style costs; nothing here certifies geometry, curvature,
        # orientation, collision or braking.
        coords = {"s": (0.0, 0.0, 0.0), "m": (3.0, 4.0, 0.0), "g": (3.0, 4.0, 12.0)}

        def distance(first, second):
            (ax, ay, az), (bx, by, bz) = coords[first], coords[second]
            return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)

        graph = CandidateGraph(
            ["s", "m", "g"],
            [
                Edge("d1", "s", "m", NormalizedCost(distance("s", "m"), 0, 0, 0, 0)),
                Edge("d2", "m", "g", NormalizedCost(distance("m", "g"), 0, 0, 0, 0)),
                Edge("d3", "s", "g", NormalizedCost(distance("s", "g"), 0, 0, 0, 0)),
            ],
        )
        expected_two_hop = Fraction(distance("s", "m")) + Fraction(distance("m", "g"))
        expected_direct = Fraction(distance("s", "g"))
        self.assertEqual(expected_two_hop, Fraction(17))
        self.assertEqual(expected_direct, Fraction(13))
        result = graph.search("s", "g", MAX_EXPANSIONS)
        self.assertEqual(result.edge_ids, ("d3",))
        self.assertEqual(result.cost, expected_direct)

class ExhaustiveReferenceTests(unittest.TestCase):
    def _all_pairs(self, fixture, graph):
        results = {}
        for start in fixture["node_ids"]:
            for goal in fixture["node_ids"]:
                results[(start, goal)] = graph.search(start, goal, MAX_EXPANSIONS)
        return results

    def test_hundred_fixed_seed_graphs_match_exhaustive_reference(self):
        graphs_seen = 0
        pairs_seen = 0
        found_total = 0
        unreachable_total = 0
        for offset in range(GRAPH_COUNT):
            seed = GRAPH_SEED_BASE + offset
            fixture = build_graph_fixture(seed)
            graph = build_graph(fixture)
            self.assertGreaterEqual(len(fixture["node_ids"]), 2)
            self.assertLessEqual(len(fixture["node_ids"]), 7)
            for start in fixture["node_ids"]:
                for goal in fixture["node_ids"]:
                    expected = reference_answer(fixture, start, goal)
                    result = graph.search(start, goal, MAX_EXPANSIONS)
                    pairs_seen += 1
                    with self.subTest(seed=seed, start=start, goal=goal):
                        if expected is None:
                            self.assertEqual(result.status, "unreachable")
                            self.assertEqual(result.edge_ids, ())
                            self.assertEqual(result.node_ids, ())
                            self.assertIsNone(result.cost)
                            self.assertEqual(
                                result.expansion_count,
                                reference_reachable_count(fixture, start),
                            )
                            unreachable_total += 1
                        else:
                            cost, hops, sequence, chain = expected
                            self.assertEqual(result.status, "found")
                            self.assertEqual(result.edge_ids, sequence)
                            self.assertEqual(result.node_ids, chain)
                            self.assertEqual(result.cost, cost)
                            self.assertEqual(len(sequence), hops)
                            self.assertLessEqual(result.expansion_count, graph.node_count)
                            found_total += 1
            graphs_seen += 1
        self.assertEqual(graphs_seen, GRAPH_COUNT)
        self.assertGreater(pairs_seen, GRAPH_COUNT)
        self.assertGreater(found_total, 0)
        self.assertGreater(unreachable_total, 0)

    def test_fixture_generation_is_deterministic_and_varied(self):
        first = [build_graph_fixture(GRAPH_SEED_BASE + index) for index in range(GRAPH_COUNT)]
        second = [build_graph_fixture(GRAPH_SEED_BASE + index) for index in range(GRAPH_COUNT)]
        self.assertEqual(first, second)
        signatures = {
            tuple(
                (edge["edge_id"], edge["source"], edge["target"], tuple(edge["components"]))
                for edge in fixture["edges"]
            )
            for fixture in first
        }
        self.assertGreater(len(signatures), 1)

    def test_fixture_structures_cover_parallel_cycles_and_unreachable(self):
        parallel = 0
        self_loops = 0
        cycles = 0
        zero_cost_cycles = 0
        unreachable_graphs = 0
        for offset in range(GRAPH_COUNT):
            fixture = build_graph_fixture(GRAPH_SEED_BASE + offset)
            multiplicity = {}
            for edge in fixture["edges"]:
                key = (edge["source"], edge["target"])
                multiplicity[key] = multiplicity.get(key, 0) + 1
            if any(count >= 2 for count in multiplicity.values()):
                parallel += 1
            if any(edge["source"] == edge["target"] for edge in fixture["edges"]):
                self_loops += 1
            if _has_directed_cycle(fixture["node_ids"], fixture["edges"]):
                cycles += 1
            zero_edges = [
                edge
                for edge in fixture["edges"]
                if all(component == 0 for component in edge["components"])
            ]
            if _has_directed_cycle(fixture["node_ids"], zero_edges):
                zero_cost_cycles += 1
            if any(
                reference_answer(fixture, start, goal) is None
                for start in fixture["node_ids"]
                for goal in fixture["node_ids"]
            ):
                unreachable_graphs += 1
        self.assertGreaterEqual(parallel, 1)
        self.assertGreaterEqual(self_loops, 1)
        self.assertGreaterEqual(cycles, 1)
        self.assertGreaterEqual(zero_cost_cycles, 1)
        self.assertGreaterEqual(unreachable_graphs, 1)

    def test_start_equals_goal_for_every_fixture_node(self):
        checked = 0
        for offset in range(GRAPH_COUNT):
            fixture = build_graph_fixture(GRAPH_SEED_BASE + offset)
            graph = build_graph(fixture)
            for node in fixture["node_ids"]:
                result = graph.search(node, node, 0)
                with self.subTest(seed=fixture["seed"], node=node):
                    self.assertEqual(result.status, "found")
                    self.assertEqual(result.edge_ids, ())
                    self.assertEqual(result.node_ids, (node,))
                    self.assertEqual(result.cost, Fraction(0))
                    self.assertEqual(result.expansion_count, 0)
                checked += 1
        self.assertGreater(checked, GRAPH_COUNT)

    def test_insertion_order_permutations_do_not_change_results(self):
        seeds = [GRAPH_SEED_BASE + offset for offset in (3, 19, 42, 77, 99)]
        for seed in seeds:
            fixture = build_graph_fixture(seed)
            baseline = self._all_pairs(fixture, build_graph(fixture))
            rng = random.Random(seed * 1000003 + 7)
            for trial in range(8):
                nodes = list(fixture["node_ids"])
                edges = list(fixture["edges"])
                rng.shuffle(nodes)
                rng.shuffle(edges)
                permuted = self._all_pairs(fixture, build_graph(fixture, nodes, edges))
                with self.subTest(seed=seed, trial=trial):
                    self.assertEqual(permuted, baseline)
            reversed_pairs = self._all_pairs(
                fixture,
                build_graph(
                    fixture,
                    list(reversed(fixture["node_ids"])),
                    list(reversed(fixture["edges"])),
                ),
            )
            with self.subTest(seed=seed, trial="reversed"):
                self.assertEqual(reversed_pairs, baseline)

    def test_expansion_count_bounded_across_suite(self):
        for offset in range(GRAPH_COUNT):
            fixture = build_graph_fixture(GRAPH_SEED_BASE + offset)
            graph = build_graph(fixture)
            for start in fixture["node_ids"]:
                for goal in fixture["node_ids"]:
                    result = graph.search(start, goal, MAX_EXPANSIONS)
                    with self.subTest(seed=fixture["seed"], start=start, goal=goal):
                        self.assertLessEqual(result.expansion_count, graph.node_count)
                        self.assertLessEqual(result.expansion_count, MAX_EXPANSIONS)


if __name__ == "__main__":
    unittest.main()
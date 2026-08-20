# QOBLIB file formats

This document describes the instance and solution file formats for each
problem class in QOBLIB.  It is the reference for anyone writing a solver,
preparing a submission, or implementing a new plugin for this library.

Each section covers:

- **Problem** — what is being optimised.
- **Objective** — what `result.objective` contains after `check_solution`.
- **Instance format** — the files under `NN-problem/instances/`.
- **Solution format** — the files under `NN-problem/solutions/`.
- **Checker CLI** — how the official Rust binary is invoked.
- **Python types** — the dataclasses returned by `load_instance` / `load_solution`.

---

## 01 — Market Split (`marketsplit`)

**Problem.** Given an integer matrix *A* (n_rows × n_cols) and a right-hand
side vector *b*, find a binary vector *x* ∈ {0,1}^n_cols such that `A x = b`.
Pure feasibility — there is no objective to minimise.

**Objective.** `0.0` when feasible.

### Instance format — `.dat`

```
# optional comment lines starting with #
<n_rows> <n_cols>
w1 w2 ... w_{n_cols} rhs
w1 w2 ... w_{n_cols} rhs
...
```

- One header line: number of constraint rows, number of variables.
- One data line per row: `n_cols` integer weights followed by the integer RHS.
- Commas are treated as whitespace.
- The RHS on each row equals `sum(weights) / 2`.

### Solution format — `.sol`

A compact binary string of length `n_cols`, one character per variable:

```
01001101...
```

`0` means variable is 0, `1` means variable is 1.  The Rust checker also
accepts whitespace/comma-separated integers and `x#N value` (MIP solver output).

### Checker CLI

```
check_marketsplit <instance.dat> <solution.sol>
```

### Python types

`MarketSplitInstance(n_rows, n_cols, A, b, name, path)`
`MarketSplitSolution(x, name, path)`

---

## 02 — LABS (`labs`)

**Problem.** Find a binary sequence *s* ∈ {−1,+1}^n that minimises the
energy `E(s) = Σ_{k=1}^{n−1} C_k(s)²`, where `C_k(s) = Σ_{i=1}^{n−k} s_i · s_{i+k}`.
The merit factor is `F = n² / (2 E(s))`.

**Objective.** Energy `E(s)` (lower is better).

### Instance format

LABS has **no instance files**.  An instance is fully defined by the sequence
length *n* (a positive integer).  The downloadable artifacts are model files
(QUBO / ILP formulations) under `02-labs/models/`.

### Solution format — `.sol`

A compact binary string of length *n*:

```
01101001...
```

`0` encodes −1, `1` encodes +1.  The Rust checker applies this mapping
internally.

### Checker CLI

```
check_labs <n> <solution.sol>
```

### Python types

Instance: plain `int` (the sequence length *n*).
`LABSSolution(s, name)` — `s` may use {−1, +1} or {0, 1} encoding.

---

## 03 — Birkhoff Decomposition (`birkhoff`)

**Problem.** Given a doubly stochastic matrix *D*, find the minimum number of
permutation matrices *P_i* and weights *λ_i* ≥ 0 such that
`D = Σ λ_i P_i` with `Σ λ_i = 1`.

**Objective.** Total number of permutation matrices used across all
sub-instances in the file.

### Instance format — `.json`

A single JSON object.  Keys starting with `_` (e.g. `_license`) are metadata
and ignored.  Each remaining key is an instance ID mapping to:

```json
{
  "id": "B5_dense_001",
  "n": 5,
  "scale": 1000,
  "scaled_doubly_stochastic_matrix": [500, 100, ...]
}
```

`scaled_doubly_stochastic_matrix` is the matrix entries listed row-by-row,
scaled by `scale` so all values are integers.

### Solution format — `.json`

Same top-level structure.  Each instance ID maps to:

```json
{
  "id": "B5_dense_001",
  "permutations": [2, 1, 4, 3, 5,   1, 2, 3, 4, 5],
  "weights": [300.0, 700.0]
}
```

`permutations` is a flat array of `k × n` 1-based column indices (k
permutations concatenated).  `weights` has length k.  `sum(weights)` must
equal `scale`.

### Checker CLI

```
check_birkhoff <instance.json> <solution.json>
```

### Python types

`BirkhoffInstance(instances, name, path)`
`BirkhoffSolution(solutions, name, path)`

---

## 04 — Node-Disjoint Steiner Trees (`steiner`)

**Problem.** Given an undirected weighted graph and several groups of
terminal nodes, find a minimum-cost set of node-disjoint Steiner trees, one
per group, each spanning all terminals in its group.

**Objective.** Total weight of all selected edges.

### Instance format — directory

Each instance is a subdirectory (e.g. `stp_s003_l1_t2_h0_rs97531/`)
containing two files:

**`arcs.dat`** — edge list:
```
# optional comments
node1 node2 weight
node1 node2 weight
...
```

**`terms.dat`** — terminal assignments:
```
node_id  network_id
node_id  network_id
...
```

Each `network_id` identifies one Steiner tree group.  A node may appear in
at most one network (node-disjointness constraint).

### Solution format — `.sol`

One selected edge per line:
```
node1 node2 network_id
node1 node2 network_id
...
```

### Checker CLI

```
check_steiner --arcs <arcs.dat> --terms <terms.dat> --sol <solution.sol>
```

### Python types

`SteinerInstance(edges, terminals, name, arcs_path, terms_path)`
`SteinerSolution(edges, name, path)`

---

## 05 — Sports Scheduling (`sports`)

**Problem.** Construct a double round-robin tournament schedule satisfying
hard and soft constraints (home/away balance, break minimisation, pattern
constraints), following the ITC2021 benchmark format.

**Objective.** Problem-specific penalty (ITC2021 cost function).

### Instance / solution format

ITC2021 XML format.  See the
[ITC2021 specification](https://sintef.github.io/sport-scheduling-problem-format/)
for the full schema.

### Checker

No official Rust checker is currently available in the QOBLIB repository.
`check_solution` raises `QoblibError` until one is added.

---

## 06 — Portfolio Optimization (`portfolio`)

**Problem.** Multi-period binary portfolio optimisation: given stock prices
and a covariance matrix, choose long/short positions to maximise risk-adjusted
return subject to a budget constraint.

**Objective.** Claimed objective value from the solution file header (exact
value verified by the Rust checker using rational arithmetic).

### Instance format — directory

Each instance is a subdirectory (e.g. `po_a010_t10_orig/`) containing:

- `stock_prices_*.csv.gz` — time-series of closing prices
- `covariance_matrices_*.csv.gz` — covariance matrices per period

The Rust checker reads these files directly; the Python library surfaces only
the directory path.

### Solution format — `.sol`

Plain text with a key-value header followed by position lines:

```
instance po_a010_t10_orig
budget 4
lambda 0.0001
objective -69482
# period  symbol  long  short
0 AAPL  0 1
1 META  1 0
```

- `budget` — integer budget *B*.
- `lambda` — risk weight λ.
- `objective` — claimed objective (integer).
- Position lines: `period symbol long_units short_units`.

### Checker CLI

```
check_portfolio <instance-dir> <solution.sol>
```

### Python types

`PortfolioInstance(instance_dir, name)`
`PortfolioSolution(instance_name, budget, lambda_, objective, positions, name, path)`

---

## 07 — Maximum Stable Set (`independentset`)

**Problem.** Find a maximum stable set (independent set) in an undirected
graph: a subset of vertices such that no two are adjacent.

**Objective.** Size of the stable set (number of selected vertices).

### Instance format — `.gph` (DIMACS, plain or gzip)

```
c optional comment
p edge <node_count> <edge_count>
e <node1> <node2>
e <node1> <node2>
...
```

Nodes are 1-based.  Files may be gzip-compressed (`.gph.gz`).

### Solution format

Either a compact binary string of length `node_count`:

```
0110100...
```

(`1` = node selected, `0` = not selected, 1-based left-to-right), or a
newline-separated list of 1-based selected node indices:

```
2
3
5
```

### Checker CLI

```
check_stableset <instance.gph> <solution.sol>
```

### Python types

`StableSetInstance(n, edges, name, path)`
`StableSetSolution(selected, name, path)`

---

## 08 — Network Design (`network`)

**Problem.** Design a directed network on *n* nodes (n ∈ {5, …, 24}) where
every node has exactly two in-edges and two out-edges.  Route a given demand
matrix through the network, minimising the maximum aggregate flow on any edge.

**Objective.** Maximum aggregate scaled flow value across all edges.

### Instance format

All instances share a single **`demand.txt`** file.  The instance is
parameterised by the node count *n* alone (encoded in the solution filename,
e.g. `network05.opt.sol` → n = 5).

**`demand.txt`**:
```
src dst demand
src dst demand
...
```

Demands are integers scaled ×1000.

### Solution format — Gurobi `.sol`

```
# Objective value = 12345.0
z 12345.0
x#1#2 1
x#2#3 0
...
f#1#1#2 500
f#1#2#3 500
...
```

- `z` — objective value.
- `x#i#j` — 1 if directed edge (i→j) is in the topology, 0 otherwise.
- `f#k#i#j` — flow of commodity *k* on edge (i→j).

### Checker CLI

```
check_network <n> <demand.txt> <solution.sol>
```

### Python types

`NetworkInstance(n, demand, demand_path, name)`
`NetworkSolution(objective, edges, flows, name, path)`

---

## 09 — Capacitated Vehicle Routing (`routing`)

**Problem.** Find minimum-cost routes from a single depot visiting all
customers, each vehicle subject to a capacity constraint (CVRP).

**Objective.** Total Euclidean route distance (rounded to nearest integer per
edge).

### Instance format — TSPLIB/CVRPLIB `.vrp`

Standard TSPLIB format with sections `NODE_COORD_SECTION`,
`DEMAND_SECTION`, and `DEPOT_SECTION`.  Key header fields:

```
NAME : E-n22-k4
DIMENSION : 22
CAPACITY : 6000
```

### Solution format

```
Route #1: 5 3 14 21 16
Route #2: 11 2 18 9 12
...
Cost 375
```

- Each `Route #k:` line lists customer node IDs (1-based, depot excluded).
- `Cost` is the total integer route cost.

### Checker CLI

```
check_cvrp <instance.vrp> <solution.sol>
```

### Python types

`CVRPInstance(name, n, capacity, coords, demands, depot, path)`
`CVRPSolution(routes, claimed_cost, name, path)`

---

## 10 — Order-Degree / Network Topology (`topology`)

**Problem.** Find an undirected graph on exactly *n* nodes where every node
has degree ≤ *d*, minimising the diameter.

**Objective.** Actual graph diameter (lower is better).

### Instance format

There are **no separate instance files**.  The instance is defined by a triple
*(n, degree, diameter)* encoded in the solution filename:

```
topology_<n>_<d>.opt.gph    ← best known optimal
topology_<n>_<d>.bst.gph    ← best known heuristic
```

The diameter is read from a comment in the graph file header (see below).

### Solution format — `.gph` (DIMACS, plain or gzip)

```
c Undirected Graph with Diameter 3
p edge <node_count> <edge_count>
e <node1> <node2>
e <node1> <node2>
...
```

Nodes are 1-based.  The `c` comment line declaring the diameter is required
by the Rust checker.  Files may be gzip-compressed.

### Checker CLI

```
check_topology <n> <degree> <diameter> <solution.gph>
```

### Python types

`TopologyInstance(n, degree, diameter, name)`
`TopologySolution(n, edges, diameter, degree, name, path)`

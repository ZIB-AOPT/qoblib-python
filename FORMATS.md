# Data and file formats

For each QOBLIB problem this document lists what the Python object holds, what a solution looks like in Python, and the file formats behind them in the [QOBLIB repository](https://github.com/ZIB-AOPT/QOBLIB). `read_solution` and `write_solution` convert between the two; `check` accepts either.

Numbering follows the files: nodes, customers and matrix columns start at 1 unless stated otherwise. Reference solution files are named `<instance>.opt.<ext>` when proven optimal and `<instance>.bst.<ext>` when best known.

## MarketSplit (`01-marketsplit`)

Find `x ∈ {0,1}^n` with `A x = b`. Feasibility problem without objective.

- **Object**: `A` (m × n integer array), `b` (length m).
- **Solution**: sequence of n zeros and ones.
- **Instance file** `instances/<name>.dat`: a line `m n`, then m lines with n weights followed by the right-hand side. `#` starts a comment.
- **Solution file**: the 0/1 values, separated by spaces. The checker also accepts a compact 0/1 string, a list of the indices set to 1, and solver output with `x#<index> <value>` lines; `read_solution` reads all of these.

## Labs (`02-labs`)

Find a sequence `s ∈ {−1,+1}^n` minimising the energy `E(s) = Σ_k C_k(s)²`, with `C_k(s) = Σ_i s_i s_{i+k}`.

- **Object**: `n`. There are no instance files.
- **Solution**: sequence of n values +1 and −1.
- **Solution file**: one character per line, `0` for +1 and `1` for −1. A Python sequence of zeros and ones is written in this encoding unchanged.
- **Objective**: the energy. The checker knows the optimum for n ≤ 66 and reports `SUBOPTIMAL` for feasible sequences above it.

## Birkhoff (`03-birkhoff`)

Write a scaled doubly stochastic matrix as a weighted sum of as few permutation matrices as possible.

- **Object**: `matrix` (n × n integer array whose rows and columns sum to `scale`), `scale`.
- **Solution**: `(weights, permutations)`. `weights` has length k and sums to `scale`; `permutations` is a k × n array in which row i gives, for each matrix row, the column of permutation i.
- **Instance file** `instances/qbench_<n>_<sparse|dense>.json`: a JSON object with ten entries, each with `id`, `n`, `scale` and `scaled_doubly_stochastic_matrix` (n² integers, row by row). An instance name is the `id`, `B<n>_<k>_<i>`, where k is the number of permutations the matrix was generated from (n for sparse, n² for dense files).
- **Solution file**: the same JSON layout, each entry with `id`, `weights` and `permutations` (the k × n values in one list). Reference solutions are the curated collections `solutions/qbench_*.json` where they exist, otherwise `solutions/<id>.bst.json`.
- **Objective**: number of permutations with non-zero weight. The reconstruction must be exact.

## Steiner (`04-steiner`)

Connect each group of terminals ("net") by a tree so that no two trees share a node, minimising the total edge cost.

- **Object**: `n_nodes`, `edges` (`{(u, v): cost}` with u < v), `terminals` (`{net: [nodes]}`), `roots` (`{net: node}`), `path` (the instance directory).
- **Solution**: list of `(u, v, net)`, one per edge used by the tree of `net`.
- **Instance directory** `instances/<name>/`: `arcs.dat` with lines `node1 node2 cost` (each edge is listed in both directions), `terms.dat` with lines `node net`, `param.dat` with `nodes <count>` and `nets <count>`, `roots.dat` with lines `node net`.
- **Solution file**: lines `node1 node2 net`.
- **Objective**: total cost of the selected edges.

## Sports (`05-sports`)

Time-constrained double round-robin scheduling in the [ITC2021 format](https://www.sportscheduling.ugent.be/ITC2021/).

- **Object**: `teams` and `slots` (names; the position is the id, starting at 0), `root` (the parsed `<Instance>` element with all constraints).
- **Solution**: list of `(home, away, slot)`.
- **Instance file** `instances/<group>/<name>.xml.gz`, **solution file** `solutions/<group>/<name>.xml.gz` with one `<ScheduledMatch home= away= slot=/>` per game. A `<name>.opt.sol` next to a schedule marks it as optimal.
- **Checker**: none in QOBLIB.

## Portfolio (`06-portfolio`)

Trade assets over several periods, balancing risk, return and transaction costs under a budget.

- **Object**: `symbols`, `prices` (days × assets), `covariances` (days × assets × assets), `budget`, `risk_aversion` (the weight λ, as a decimal string), `path` (the data directory).
- **Solution**: list of `(period, symbol, long, short)` with the units held long and short; positions not listed are zero.
- **Instance directory** `instances/<name>/`: `stock_prices.txt.gz` with lines `day symbol price` and `covariance_matrices.txt.gz` with lines `day symbol symbol value`. The benchmark instances combine each data set with a budget and a λ; `instances/manifest.json` lists the grid.
- **Solution file** `solutions/<name>/<name>_b<budget>_l<lambda>.<opt|bst>.sol`: optional header lines `instance`, `budget`, `lambda`, `objective`, then lines `period symbol long short`. Files written by this package contain only the position lines; budget and λ are passed to the checker from the object.
- **Objective**: the integer value computed by the checker (smaller is better). A file that claims a different `objective` in its header is reported as `INVALID_FILE`.

## IndependentSet (`07-independentset`)

Find a largest set of pairwise non-adjacent nodes.

- **Object**: `n`, `edges` (m × 2 integer array).
- **Solution**: collection of node numbers.
- **Instance file** `instances/<name>.gph`: DIMACS format with a line `p edge <nodes> <edges>` and lines `e <node1> <node2>`; lines starting with `c` are comments.
- **Solution file**: one node number per line; `#` starts a comment.
- **Objective**: size of the set.

## Network (`08-network`)

Choose a directed network on n nodes in which every node has exactly two incoming and two outgoing edges, and route all demands so that the largest total flow on an edge is minimal.

- **Object**: `n`, `demand` (n × n array; entry `[i-1, j-1]` is the demand from i to j). All sizes use the top-left part of one 24-node matrix, `instances/demand.txt`.
- **Solution**: `(edges, flows)`: the list of edges `(i, j)` and `{(k, i, j): flow}`, the flow on edge (i, j) that originates at node k. Flows are integers, 1000 times the unit of `demand`.
- **Solution file** `solutions/network<n>.<opt|bst>.sol`: solver output with lines `x#<i>#<j> <0|1>` and `f#<k>#<i>#<j> <flow>`, plus `z <objective>`; `#` at the start of a line is a comment.
- **Objective**: the largest total flow on an edge, as recomputed by the checker.

## Routing (`09-routing`)

Capacitated vehicle routing with one depot.

- **Object**: `capacity`, `coords` (dimension × 2), `demands`, `depot`.
- **Solution**: list of routes, each the list of customers one vehicle visits in order, without the depot.
- **Instance file** `instances/<name>.vrp`: TSPLIB/CVRPLIB format with `DIMENSION`, `CAPACITY`, `NODE_COORD_SECTION`, `DEMAND_SECTION` and `DEPOT_SECTION`.
- **Solution file**: lines `Route #<k>: <customers>` and optionally `Cost <total>`.
- **Objective**: total distance, with Euclidean distances rounded to the nearest integer.

## Topology (`10-topology`)

Find a graph with n nodes and maximum degree d whose diameter is as small as possible.

- **Object**: `n`, `degree`, and `bounds` (lower and upper diameter bound from `instances/bounds.csv`, where listed).
- **Solution**: the edges of the graph, as an m × 2 array or a list of `(u, v)`.
- **Instance file** `instances/topology_<n>_<d>.dat`: the two numbers.
- **Solution file** `solutions/topology_<n>_<d>.<opt|bst>.gph[.xz]`: DIMACS format as for IndependentSet.
- **Objective**: the diameter. The graph must be connected with exactly n nodes and no degree above d; with `check(..., max_diameter=D)` a larger diameter is infeasible as well.

import os
import sys
import math
import random

import numpy as np

from nodes import Node, Route

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

try:
    import vrp_logic as _logic
    LOGIC_OK = True
except ImportError as _ie:
    print(f"[vrp] vrp_logic.py not found — {_ie}")
    LOGIC_OK = False


# ── Distance matrix ────────────────────────────────────────────────────────────

def build_distance_matrix(depot: Node, customers: list) -> np.ndarray:
    nodes = [(depot.x, depot.y)] + [(c.x, c.y) for c in customers]
    n     = len(nodes)
    mat   = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            dx = nodes[i][0] - nodes[j][0]
            dy = nodes[i][1] - nodes[j][1]
            mat[i][j] = (dx * dx + dy * dy) ** 0.5
    return mat


# ── Chromosome → Route objects ─────────────────────────────────────────────────

def decode_chromosome(chrom: list, customers: list) -> list:
    routes = []
    vid    = 0
    cur    = []
    for g in chrom:
        if g == 0:
            r = Route(vid)
            r.nodes = [customers[x - 1] for x in cur]
            routes.append(r)
            vid += 1
            cur  = []
        else:
            cur.append(g)
    if cur:
        r = Route(vid)
        r.nodes = [customers[x - 1] for x in cur]
        routes.append(r)
    return routes


# ── Main GA entry point ────────────────────────────────────────────────────────

def run_ga(depot: Node, customers: list, demands: list,
           n_vehicles: int, v_cap: int,
           pop_size: int, n_gen: int):
    """
    Returns (routes, fitness_history).
    fitness_history is a list of (best_fitness, avg_fitness) per generation.
    """
    if not LOGIC_OK or not customers:
        return [], []

    matrix    = build_distance_matrix(depot, customers)
    total_d   = sum(demands[1:])
    min_v     = math.ceil(total_d / v_cap)
    actual_v  = max(n_vehicles, min_v)

    population = _logic.initialization_population(
        pop_size, demands, actual_v, v_cap, len(customers)
    )

    history    = []
    best_route = None
    best_fit   = -1.0
    elite_k    = max(1, int(0.2 * pop_size))

    for _ in range(n_gen):
        fits = [_logic.fitness(ind, matrix, demands, v_cap) for ind in population]
        gb   = max(fits)
        ga_  = sum(fits) / len(fits)
        history.append((gb, ga_))

        bi = fits.index(gb)
        if gb > best_fit:
            best_fit   = gb
            best_route = population[bi]

        sp  = sorted(zip(fits, population), reverse=True)
        new = [ind for _, ind in sp[:elite_k]]
        ri  = random.randint(elite_k, pop_size - 1)
        new.append(sp[ri][1])

        while len(new) < pop_size:
            p1 = _logic.selection(population, fits)
            p2 = _logic.selection(population, fits)
            new.append(_logic.order_crossover(p1, p2, demands, v_cap))

        new        = _logic.mutate_population(new)
        population = new

    return decode_chromosome(best_route, customers), history

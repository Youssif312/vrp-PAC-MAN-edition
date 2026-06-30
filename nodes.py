import math
import pygame
from dataclasses import dataclass, field
from typing import List, Tuple

from constants import VEHICLE_COLORS, PX_TO_KM


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class Node:
    x: float
    y: float
    idx: int
    demand: int = 1


@dataclass
class Route:
    vehicle_id: int
    nodes: List[Node] = field(default_factory=list)


# ── Geometry helpers ───────────────────────────────────────────────────────────

def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def route_dist_nodes(depot, nodes) -> float:
    if not nodes:
        return 0.0
    d = dist(depot, nodes[0])
    for i in range(len(nodes) - 1):
        d += dist(nodes[i], nodes[i + 1])
    d += dist(nodes[-1], depot)
    return d


def total_route_distance(depot, route) -> float:
    return route_dist_nodes(depot, route.nodes)


def route_km(depot, route) -> float:
    return total_route_distance(depot, route) * PX_TO_KM


def build_waypoints(depot, route) -> List[Tuple[float, float]]:
    pts = [(depot.x, depot.y)]
    for n in route.nodes:
        pts.append((n.x, n.y))
    pts.append((depot.x, depot.y))
    return pts


# ── Truck drawing ──────────────────────────────────────────────────────────────

def draw_truck(surf, x, y, angle_rad, color, scale=1.0):
    r   = int(12 * scale)
    t   = pygame.time.get_ticks() / 1000.0
    mouth = abs(math.sin(t * 8)) * 35
    mr  = math.radians(mouth)
    cx, cy = int(x), int(y)
    pts = [(cx, cy)]
    sa  = angle_rad + mr
    ea  = angle_rad + 2 * math.pi - mr
    for i in range(31):
        a = sa + (ea - sa) * i / 30
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    sh = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
    pygame.draw.polygon(sh, (0, 0, 0, 50),
                        [(p[0] - cx + r * 2 + 3, p[1] - cy + r * 2 + 3) for p in pts])
    surf.blit(sh, (cx - r * 2, cy - r * 2))
    pygame.draw.polygon(surf, color, pts)
    ex = cx + int(r * 0.35 * math.cos(angle_rad - math.pi / 2))
    ey = cy + int(r * 0.35 * math.sin(angle_rad - math.pi / 2))
    pygame.draw.circle(surf, (0, 0, 0), (ex, ey), max(2, int(2.5 * scale)))


# ── Animated truck state ───────────────────────────────────────────────────────

@dataclass
class TruckAnim:
    route:     Route
    waypoints: List[Tuple[float, float]]
    color:     Tuple[int, int, int]
    seg_idx:   int   = 0
    seg_t:     float = 0.0
    done:      bool  = False
    trail:        List[Tuple[float, float]] = field(default_factory=list)
    visited:      set                       = field(default_factory=set)
    flash_timers: dict                      = field(default_factory=dict)

    def current_pos(self) -> Tuple[float, float]:
        if self.seg_idx >= len(self.waypoints) - 1:
            return self.waypoints[-1]
        ax, ay = self.waypoints[self.seg_idx]
        bx, by = self.waypoints[self.seg_idx + 1]
        return (ax + (bx - ax) * self.seg_t, ay + (by - ay) * self.seg_t)

    def current_angle(self) -> float:
        if self.seg_idx >= len(self.waypoints) - 1:
            return 0.0
        ax, ay = self.waypoints[self.seg_idx]
        bx, by = self.waypoints[self.seg_idx + 1]
        return math.atan2(by - ay, bx - ax)

    def advance(self, dt: float, speed: float):
        if self.done:
            return
        wps = self.waypoints
        while dt > 0:
            if self.seg_idx >= len(wps) - 1:
                self.done = True
                return
            ax, ay = wps[self.seg_idx]
            bx, by = wps[self.seg_idx + 1]
            sl = math.hypot(bx - ax, by - ay)
            if sl < 0.5:
                self.seg_idx += 1
                self.seg_t = 0.0
                continue
            rem = (1.0 - self.seg_t) * sl
            df  = speed * dt
            if df < rem:
                self.seg_t += df / sl
                dt = 0
            else:
                dt -= rem / speed
                self.seg_idx += 1
                self.seg_t = 0.0
                wp = self.seg_idx
                if 1 <= wp <= len(self.route.nodes):
                    n = self.route.nodes[wp - 1]
                    self.visited.add(n.idx)
                    self.flash_timers[n.idx] = 0.5
        self.trail.append(self.current_pos())
        if len(self.trail) > 30:
            self.trail.pop(0)

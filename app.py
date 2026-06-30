import math
import random
import pygame
from typing import List, Optional, Tuple

from constants import (
    W, H, BG, BORDER, PANEL_BG, TEXT_PRI, TEXT_SEC, DEPOT_COL, ACCENT,
    BTN_BG, BTN_HOV, BTN_SOLVE, BTN_SOLVE_H, BTN_CLR, BTN_CLR_H,
    BTN_RAND, BTN_RAND_H, ROUTE_ALPHA,
    CANVAS_X, CANVAS_W, GRAPH_H, GRAPH_Y,
    NODE_R, DEPOT_R, PANEL_W, VEHICLE_COLORS,
)
from nodes   import Node, Route, TruckAnim, draw_truck, build_waypoints, route_km, total_route_distance
from sound   import SoundManager
from widgets import Button, Spinbox, Slider
from screens import DemandInputScreen, FitnessGraph
from ga_runner import run_ga, LOGIC_OK

from dataset_loader   import DatasetPanel, load_addresses, ADDRESSES_FILE
from solution_exporter import export_solution_pdf


# ── Helper: pixel font ─────────────────────────────────────────────────────────

def _pxfont(sz, bold=False):
    for name in ("Press Start 2P", "Courier New", "monospace"):
        try:
            return pygame.font.SysFont(name, sz, bold=bold)
        except Exception:
            pass
    return pygame.font.SysFont("monospace", sz, bold=bold)


# ── Main application ───────────────────────────────────────────────────────────

class VRPApp:
    #NEW------------------------------------
    def _inject_dataset(self, depot_d: dict, customers_d: list):

        import math
        from nodes import Node

        # canvas bounds
        mg = 60
        cx0 = CANVAS_X + mg;
        cx1 = W - mg
        cy0 = mg;
        cy1 = GRAPH_Y - mg
        cw = cx1 - cx0;
        ch = cy1 - cy0

        # find bounding box of raw data
        all_x = [depot_d["x"]] + [c["x"] for c in customers_d]
        all_y = [depot_d["y"]] + [c["y"] for c in customers_d]
        rx0, rx1 = min(all_x), max(all_x)
        ry0, ry1 = min(all_y), max(all_y)
        rw = max(rx1 - rx0, 1);
        rh = max(ry1 - ry0, 1)

        def scale(x, y):
            sx = cx0 + (x - rx0) / rw * cw
            sy = cy0 + (y - ry0) / rh * ch
            return sx, sy

        # reset everything
        self.customers.clear()
        self.routes.clear()
        self.trucks.clear()
        self.node_ctr = 0
        self.fitness_history = []
        self.fitness_graph.reset()

        dx, dy = scale(depot_d["x"], depot_d["y"])
        self.depot = Node(dx, dy, -1)

        for c in customers_d:
            sx, sy = scale(c["x"], c["y"])
            self.customers.append(Node(sx, sy, self.node_ctr, demand=c["demand"]))
            self.node_ctr += 1

        self._rebuild_demands()
        self.sound.play("randomize")
        self.status = (f"Loaded {len(self.customers)} customers from dataset. "
                       f"Press SOLVE.")
    # ── Init ───────────────────────────────────────────────────────────────────

    def __init__(self):
        #NEW
        self.demand_screen = None
        self.dataset_panel: Optional[DatasetPanel] = None
        self.addresses: dict = {}

        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("PAC-VRP Solver")

        self.font_lg = _pxfont(20, bold=True)
        self.font_md = _pxfont(16)
        self.font_sm = _pxfont(14)
        self.font_xs = _pxfont(13)

        self.sound = SoundManager()

        # State
        self.depot:   Optional[Node]  = None
        self.customers: List[Node]    = []
        self.routes:    List[Route]   = []
        self.trucks:    List[TruckAnim] = []
        self.node_ctr  = 0
        self.demands:  List[int]      = []
        self.v_capacity = 10

        # Interaction flags
        self.placing_depot   = False
        self.dragging_node:  Optional[Node] = None
        self.drag_offset     = (0, 0)
        self.animating       = False
        self.paused          = False

        # UI / output state
        self.status          = "Click canvas to add customers, or Randomize."
        self.route_revealed: List[float]            = []
        self.fitness_history: List[Tuple[float, float]] = []
        self.demand_screen:  Optional[DemandInputScreen] = None

        self._init_widgets()
        gm = 6
        self.fitness_graph = FitnessGraph(
            CANVAS_X + gm, GRAPH_Y + gm,
            CANVAS_W - gm * 2, GRAPH_H - gm * 2,
            self.font_sm, self.font_xs,
        )
        self.clock      = pygame.time.Clock()
        self.trail_surf = pygame.Surface((W, H), pygame.SRCALPHA)

    def _init_widgets(self):
        px = 10
        pw = PANEL_W - 20
        BH = 32
        GAP = 6
        y  = 82

        self._stats_y = y
        y += 4 * 20 + 6
        self._sep   = []
        self._lbl_y = {}

        self._sep.append(y); y += GAP
        self._lbl_y['vehicles'] = y; y += 16
        self.spin_vehicles = Spinbox((px, y, pw, BH), 3, 1, 8, self.font_sm); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['capacity'] = y; y += 16
        self.spin_capacity = Spinbox((px, y, pw, BH), 10, 1, 999, self.font_sm); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['gens'] = y; y += 16
        self.spin_gen = Spinbox((px, y, pw, BH), 200, 20, 500, self.font_xs); y += BH + GAP
        self._lbl_y['pop'] = y; y += 16
        self.spin_pop = Spinbox((px, y, pw, BH), 50, 20, 300, self.font_xs); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['rand_count'] = y; y += 16
        self.spin_rand_count = Spinbox((px, y, pw, BH), 15, 3, 50, self.font_xs); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['speed'] = y; y += 16
        self.slider = Slider((px, y + 16, pw, 14), 30, 500, 150.0, self.font_xs, "Speed px/s")
        y += 16 + 14 + GAP + 4

        self._sep.append(y); y += GAP
        self._lbl_y['actions'] = y; y += 16
        hw = (pw - 4) // 2
        self.btn_depot    = Button((px,      y, hw, BH), "DEPOT",  BTN_BG,    BTN_HOV,    self.font_xs)
        self.btn_rand_all = Button((px+hw+4, y, hw, BH), "RANDOM", BTN_RAND,  BTN_RAND_H, self.font_xs)
        y += BH + GAP
        self.btn_solve = Button((px,      y, hw, BH), "SOLVE", BTN_SOLVE, BTN_SOLVE_H, self.font_xs)
        self.btn_clear = Button((px+hw+4, y, hw, BH), "CLEAR", BTN_CLR,  BTN_CLR_H,  self.font_xs)
        y += BH + GAP + 4

        #NEW
        self._sep.append(y);
        y += GAP
        self._lbl_y['dataset'] = y;
        y += 16
        self.btn_dataset = Button(
            (px, y, pw, BH), "ADD DATASET", BTN_RAND, BTN_RAND_H, self.font_xs
        );
        y += BH + GAP
        self.btn_export = Button(
            (px, y, pw, BH), "EXTRACT PDF", BTN_SOLVE, BTN_SOLVE_H, self.font_xs
        );
        y += BH + GAP + 4

        self._sep.append(y); y += GAP
        self._routes_y = y

    # ── Canvas helpers ─────────────────────────────────────────────────────────

    def canvas_rect(self):
        return pygame.Rect(CANVAS_X, 0, CANVAS_W, GRAPH_Y)

    def node_at(self, x, y) -> Optional[Node]:
        candidates = ([self.depot] if self.depot else []) + self.customers
        for n in candidates:
            if n and math.hypot(n.x - x, n.y - y) <= NODE_R + 5:
                return n
        return None

    # ── State mutators ─────────────────────────────────────────────────────────

    def add_customer(self, x, y):
        self.customers.append(Node(x, y, self.node_ctr, demand=1))
        self.node_ctr += 1
        self.routes   = []
        self.trucks   = []
        self.sound.play("click")

    def _rebuild_demands(self):
        self.demands = [0] + [c.demand for c in self.customers]

    def randomize_all(self):
        n   = self.spin_rand_count.value
        mg  = 50
        x0, x1 = CANVAS_X + mg, W - mg
        y0, y1 = mg, GRAPH_Y - mg
        self.customers.clear()
        self.routes.clear()
        self.trucks.clear()
        self.node_ctr       = 0
        self.fitness_history = []
        self.fitness_graph.reset()

        cap = self.spin_capacity.value
        for _ in range(n):
            d = random.randint(1, max(1, cap // 3))
            self.customers.append(
                Node(random.randint(x0, x1), random.randint(y0, y1), self.node_ctr, demand=d)
            )
            self.node_ctr += 1

        dx, dy = x0, y0
        for _ in range(300):
            dx = random.randint(x0, x1)
            dy = random.randint(y0, y1)
            if all(math.hypot(dx - c.x, dy - c.y) > 40 for c in self.customers):
                break
        self.depot = Node(dx, dy, -1)
        self._rebuild_demands()
        self.sound.play("randomize")
        self.status = f"Randomised {n} customers. Press SOLVE."

    def clear(self):
        self.depot  = None
        self.customers.clear()
        self.routes.clear()
        self.trucks.clear()
        self.node_ctr        = 0
        self.animating       = False
        self.paused          = False
        self.fitness_history = []
        self.fitness_graph.reset()
        self.demands         = []
        self.demand_screen   = None
        self.status          = "Canvas cleared."
        self.sound.play("clear")

    # ── Solve flow ─────────────────────────────────────────────────────────────

    def solve(self):
        if not self.depot:
            self.status = "Place a depot first!"
            return
        if not self.customers:
            self.status = "Add customers first."
            return
        if not LOGIC_OK:
            self.status = "vrp_logic.py missing next to this file!"
            return
        self._rebuild_demands()
        self.demand_screen = DemandInputScreen(
            self.screen, self.customers,
            self.font_lg, self.font_md, self.font_sm, self.font_xs,
        )

    def _run_ga_after_demands(self):
        for i, c in enumerate(self.customers):
            c.demand = self.demand_screen.demands[i]
        self._rebuild_demands()
        self.demand_screen = None

        self.v_capacity = self.spin_capacity.value
        n_vehicles      = self.spin_vehicles.value
        total_d         = sum(self.demands[1:])
        max_single      = max(self.demands[1:])

        if self.v_capacity < max_single:
            self.status = (f"BLOCKED: Capacity {self.v_capacity} too low! "
                           f"Customer needs {max_single}. Raise CAPACITY.")
            return

        min_v = math.ceil(total_d / self.v_capacity)
        if n_vehicles < min_v:
            self.status = (f"BLOCKED: {n_vehicles} truck(s) not enough. "
                           f"Need >={min_v} (demand {total_d} / cap {self.v_capacity}). "
                           f"Raise VEHICLES.")
            return

        self.status = "Running GA...  please wait."
        self.screen.fill(BG)
        self.draw_panel(self.screen)
        pygame.display.flip()
        self.sound.play("solve")

        self.routes, self.fitness_history = run_ga(
            self.depot, self.customers, self.demands,
            n_vehicles, self.v_capacity,
            self.spin_pop.value, self.spin_gen.value,
        )
        self.fitness_graph.update(self.fitness_history)

        total_k = sum(route_km(self.depot, r) for r in self.routes)
        bf      = self.fitness_history[-1][0] if self.fitness_history else 0.0
        self.status = (f"Done  |  {len(self.routes)} routes  "
                       f"|  {total_k:.2f}km  |  fit {bf:.4f}")
        self._start_animation()

    # ── Animation ──────────────────────────────────────────────────────────────

    def _start_animation(self):
        self.trucks = []
        for r in self.routes:
            col = VEHICLE_COLORS[r.vehicle_id % len(VEHICLE_COLORS)]
            tk  = TruckAnim(route=r, waypoints=build_waypoints(self.depot, r), color=col)
            if not r.nodes:
                tk.done = True
            self.trucks.append(tk)
        self.route_revealed = [0.0] * len(self.routes)
        self.animating      = True
        self.paused         = False

    def update_animation(self, dt: float):
        if not self.animating or self.paused:
            return
        speed    = self.slider.value
        all_done = True
        for ti, tk in enumerate(self.trucks):
            if tk.done:
                continue
            all_done = False
            prev     = set(tk.visited)
            tk.advance(dt, speed)
            for _ in tk.visited - prev:
                self.sound.play("waka")
            for k in list(tk.flash_timers):
                tk.flash_timers[k] -= dt
                if tk.flash_timers[k] <= 0:
                    del tk.flash_timers[k]
            if ti < len(self.route_revealed):
                wps = tk.waypoints
                seg = tk.seg_idx
                rev = sum(
                    math.hypot(wps[i+1][0]-wps[i][0], wps[i+1][1]-wps[i][1])
                    for i in range(min(seg, len(wps) - 1))
                )
                if seg < len(wps) - 1:
                    sl  = math.hypot(wps[seg+1][0]-wps[seg][0], wps[seg+1][1]-wps[seg][1])
                    rev += sl * tk.seg_t
                self.route_revealed[ti] = rev

        if all_done and self.trucks:
            self.animating = False
            for ti, r in enumerate(self.routes):
                self.route_revealed[ti] = total_route_distance(self.depot, r)
            self.status = "All trucks returned to depot!"
            self.sound.play("victory")

    # ── Drawing ────────────────────────────────────────────────────────────────

    def draw_grid(self, surf):
        for gx in range(CANVAS_X + 20, W, 40):
            for gy in range(20, GRAPH_Y, 40):
                pygame.draw.circle(surf, (28, 28, 85), (gx, gy), 1)

    def draw_routes_static(self, surf):
        if not self.routes or not self.depot:
            return
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for ri, r in enumerate(self.routes):
            col = VEHICLE_COLORS[r.vehicle_id % len(VEHICLE_COLORS)]
            wps = build_waypoints(self.depot, r)
            rev = self.route_revealed[ri] if ri < len(self.route_revealed) else 0.0

            # faint full path
            for i in range(len(wps) - 1):
                pygame.draw.line(s, (*col, 22),
                                 (int(wps[i][0]),   int(wps[i][1])),
                                 (int(wps[i+1][0]), int(wps[i+1][1])), 1)

            # revealed segment
            dd = 0.0
            for i in range(len(wps) - 1):
                if dd >= rev:
                    break
                ax, ay = wps[i]
                bx, by = wps[i + 1]
                sl     = math.hypot(bx - ax, by - ay)
                if dd + sl <= rev:
                    pygame.draw.line(s, (*col, ROUTE_ALPHA),
                                     (int(ax), int(ay)), (int(bx), int(by)), 2)
                    if sl > 20:
                        mx2, my2 = (ax + bx) / 2, (ay + by) / 2
                        ux, uy   = (bx - ax) / sl, (by - ay) / sl
                        a1 = (mx2 - ux*8 - uy*4, my2 - uy*8 + ux*4)
                        a2 = (mx2 - ux*8 + uy*4, my2 - uy*8 - ux*4)
                        pygame.draw.polygon(s, (*col, 180),
                                            [(int(mx2), int(my2)),
                                             (int(a1[0]), int(a1[1])),
                                             (int(a2[0]), int(a2[1]))])
                    dd += sl
                else:
                    f  = (rev - dd) / max(sl, 0.001)
                    ex = ax + (bx - ax) * f
                    ey = ay + (by - ay) * f
                    pygame.draw.line(s, (*col, ROUTE_ALPHA),
                                     (int(ax), int(ay)), (int(ex), int(ey)), 2)
                    break
        surf.blit(s, (0, 0))

    def draw_trails(self, surf):
        s = self.trail_surf
        s.fill((0, 0, 0, 0))
        for tk in self.trucks:
            tl = tk.trail
            if len(tl) < 2:
                continue
            n = len(tl)
            for i in range(1, n):
                pygame.draw.line(
                    s, (*tk.color, int(150 * i / n)),
                    (int(tl[i-1][0]), int(tl[i-1][1])),
                    (int(tl[i][0]),   int(tl[i][1])),
                    max(1, int(4 * i / n)),
                )
        surf.blit(s, (0, 0))

    def draw_nodes(self, surf):
        # collect active flash timers
        af = {}
        for tk in self.trucks:
            for ni, t in tk.flash_timers.items():
                af[ni] = max(af.get(ni, 0.0), t)

        for n in self.customers:
            vis = any(n.idx in t.visited for t in self.trucks)
            fl  = af.get(n.idx, 0.0)
            if fl > 0.0:
                fr2 = fl / 0.5
                fa  = int(255 * fr2)
                fr  = int(NODE_R + 14 * (1.0 - fr2))
                fs  = pygame.Surface((fr * 4, fr * 4), pygame.SRCALPHA)
                pygame.draw.circle(fs, (255, 255, 0, fa), (fr * 2, fr * 2), fr, 2)
                surf.blit(fs, (int(n.x) - fr * 2, int(n.y) - fr * 2))
            if not vis:
                pygame.draw.circle(surf, (210, 210, 170), (int(n.x), int(n.y)), 5)
                pygame.draw.circle(surf, (255, 255, 200), (int(n.x), int(n.y)), 3)
            else:
                pygame.draw.circle(surf, (55, 55, 25), (int(n.x), int(n.y)), 5, 1)
            it = self.font_xs.render(f"{n.idx}|{n.demand}", True,
                                     (255, 255, 0) if not vis else (70, 70, 35))
            surf.blit(it, it.get_rect(center=(int(n.x), int(n.y) - 13)))

        # depot
        if self.depot:
            d     = self.depot
            t2    = pygame.time.get_ticks() / 1000.0
            pulse = int(DEPOT_R + 2.5 * abs(math.sin(t2 * 2.5)))
            gs    = pygame.Surface((pulse * 4, pulse * 4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, 255, 0, 50), (pulse * 2, pulse * 2), pulse * 2)
            surf.blit(gs, (int(d.x) - pulse * 2, int(d.y) - pulse * 2))
            pygame.draw.circle(surf, (0, 0, 0),    (int(d.x), int(d.y)), pulse + 2)
            pygame.draw.circle(surf, DEPOT_COL,    (int(d.x), int(d.y)), pulse)
            pygame.draw.circle(surf, (255, 255, 180),(int(d.x), int(d.y)), pulse // 2)
            dt2 = self.font_xs.render("D", True, (0, 0, 0))
            surf.blit(dt2, dt2.get_rect(center=(int(d.x), int(d.y))))

    def draw_trucks(self, surf):
        for tk in self.trucks:
            if tk.done:
                continue
            px2, py2 = tk.current_pos()
            draw_truck(surf, px2, py2, tk.current_angle(), tk.color)
            v = self.font_xs.render(f"V{tk.route.vehicle_id + 1}", True, (255, 255, 0))
            surf.blit(v, (int(px2) + 14, int(py2) - 14))

    def draw_panel(self, surf):
        pygame.draw.rect(surf, PANEL_BG, (0, 0, PANEL_W, H))
        pygame.draw.line(surf, BORDER, (PANEL_W, 0), (PANEL_W, H), 2)

        # title
        surf.blit(self.font_lg.render("PAC-VRP", True, TEXT_PRI), (10, 8))
        mute_col = ACCENT if self.sound._enabled else (160, 50, 50)
        surf.blit(self.font_xs.render(
            "M:mute" if self.sound._enabled else "M:unmute", True, mute_col), (10, 32))
        lc = (0, 200, 70) if LOGIC_OK else (220, 60, 60)
        surf.blit(self.font_xs.render(
            "logic:ok" if LOGIC_OK else "logic:MISS", True, lc), (10, 46))
        pygame.draw.line(surf, BORDER, (8, 62), (PANEL_W - 8, 62), 1)

        # stats
        all_done  = bool(self.trucks) and all(t.done for t in self.trucks)
        anim_str  = ("DONE!"   if all_done else
                     "PAUSED"  if self.paused else
                     "RUNNING" if self.animating else "IDLE")
        anim_col  = ((80, 220, 100) if all_done else
                     ACCENT          if self.animating and not self.paused else TEXT_PRI)
        y = self._stats_y
        for lbl, val, vc in [
            ("DEPOT",  "YES" if self.depot else "NO",  TEXT_PRI),
            ("NODES",  str(len(self.customers)),        TEXT_PRI),
            ("ROUTES", str(len(self.routes)),           TEXT_PRI),
            ("STATE",  anim_str,                        anim_col),
        ]:
            surf.blit(self.font_xs.render(lbl, True, TEXT_SEC), (10, y))
            vt = self.font_xs.render(val, True, vc)
            surf.blit(vt, (PANEL_W - 10 - vt.get_width(), y))
            y += 20

        # separators & spinboxes/sliders
        for sy in self._sep:
            pygame.draw.line(surf, BORDER, (8, sy), (PANEL_W - 8, sy), 1)
        surf.blit(self.font_xs.render("VEHICLES",   True, TEXT_SEC), (10, self._lbl_y['vehicles']))
        self.spin_vehicles.draw(surf)
        surf.blit(self.font_xs.render("CAPACITY",   True, TEXT_SEC), (10, self._lbl_y['capacity']))
        self.spin_capacity.draw(surf)
        surf.blit(self.font_xs.render("GENERATIONS",True, TEXT_SEC), (10, self._lbl_y['gens']))
        self.spin_gen.draw(surf)
        surf.blit(self.font_xs.render("POPULATION", True, TEXT_SEC), (10, self._lbl_y['pop']))
        self.spin_pop.draw(surf)
        surf.blit(self.font_xs.render("RAND COUNT", True, TEXT_SEC), (10, self._lbl_y['rand_count']))
        self.spin_rand_count.draw(surf)
        surf.blit(self.font_xs.render("ANIM SPEED", True, TEXT_SEC), (10, self._lbl_y['speed']))
        self.slider.draw(surf)
        surf.blit(self.font_xs.render("ACTIONS",    True, TEXT_SEC), (10, self._lbl_y['actions']))
        self.btn_depot.draw(surf)
        self.btn_rand_all.draw(surf)
        self.btn_solve.draw(surf)
        self.btn_clear.draw(surf)

        #NEW--------------------------------------
        surf.blit(self.font_xs.render("DATASET / EXPORT", True, TEXT_SEC),
                  (10, self._lbl_y['dataset']))
        self.btn_dataset.draw(surf)
        self.btn_export.draw(surf)

        # route list
        ROUTE_SECTION_H = 170
        route_top = H - ROUTE_SECTION_H
        pygame.draw.line(surf, BORDER, (8, route_top), (PANEL_W - 8, route_top), 1)
        surf.blit(self.font_xs.render("ROUTES  (km)", True, TEXT_SEC), (10, route_top + 4))
        if self.routes and self.depot:
            for i, r in enumerate(self.routes[:6]):
                col = VEHICLE_COLORS[r.vehicle_id % len(VEHICLE_COLORS)]
                ry  = route_top + 20 + i * 22
                pygame.draw.circle(surf, col, (18, ry + 7), 5)
                tk         = next((t for t in self.trucks if t.route.vehicle_id == r.vehicle_id), None)
                done_mark  = "✓" if tk and tk.done else " "
                km         = route_km(self.depot, r)
                total_d    = sum(n.demand for n in r.nodes)
                txt        = f"V{r.vehicle_id+1} {done_mark}  {len(r.nodes)}stops  {km:.2f}km  d:{total_d}"
                info       = self.font_xs.render(txt, True, col if (tk and tk.done) else TEXT_PRI)
                surf.blit(info, (28, ry))
        else:
            nh = self.font_xs.render("No routes yet", True, TEXT_SEC)
            surf.blit(nh, (10, route_top + 22))

        # status bar
        pygame.draw.line(surf, BORDER, (8, H - 38), (PANEL_W - 8, H - 38), 1)
        words = self.status.split()
        ln    = ""
        lines = []
        for w in words:
            t = (ln + " " + w).strip()
            if self.font_xs.size(t)[0] > PANEL_W - 18:
                lines.append(ln)
                ln = w
            else:
                ln = t
        if ln:
            lines.append(ln)
        for i, l in enumerate(lines[:2]):
            surf.blit(self.font_xs.render(l, True, TEXT_PRI), (10, H - 33 + i * 14))

    def draw_cursor_hint(self, surf):
        if not self.placing_depot:
            return
        mx, my = pygame.mouse.get_pos()
        if self.canvas_rect().collidepoint(mx, my):
            s = pygame.Surface((DEPOT_R * 4, DEPOT_R * 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*DEPOT_COL, 90), (DEPOT_R * 2, DEPOT_R * 2), DEPOT_R, 2)
            surf.blit(s, (mx - DEPOT_R * 2, my - DEPOT_R * 2))
            ht = self.font_xs.render("click to place depot", True, DEPOT_COL)
            surf.blit(ht, (mx + 14, my - 6))

    # ── Event handling ─────────────────────────────────────────────────────────

    def _handle_canvas_click(self, mx, my, button):
        if button == 1:
            if self.placing_depot:
                self.depot         = Node(mx, my, -1)
                self.placing_depot = False
                self.routes        = []
                self.trucks        = []
                self.status        = "Depot placed. Press SOLVE."
                self.sound.play("depot")
            else:
                hit = self.node_at(mx, my)
                if hit:
                    self.dragging_node = hit
                    self.drag_offset   = (hit.x - mx, hit.y - my)
                elif not self.animating:
                    self.add_customer(mx, my)
                    self.status = f"Added node #{self.node_ctr - 1}."
        elif button == 3 and not self.animating:
            hit = self.node_at(mx, my)
            if hit:
                if hit is self.depot:
                    self.depot  = None
                    self.routes = []
                    self.trucks = []
                    self.status = "Depot removed."
                else:
                    self.customers.remove(hit)
                    self.routes = []
                    self.trucks = []
                    self.status = f"Removed node #{hit.idx}."

    def _handle_keydown(self, ev):
        k = ev.key
        if   k == pygame.K_ESCAPE:                        self.placing_depot = False
        elif k == pygame.K_RETURN:                        self.solve()
        elif k in (pygame.K_DELETE, pygame.K_BACKSPACE):  self.clear()
        elif k == pygame.K_SPACE:
            if self.animating or self.paused:
                self.paused = not self.paused
        elif k == pygame.K_r:  self.randomize_all()
        elif k == pygame.K_m:
            on = self.sound.toggle()
            self.status = f"Sound {'ON' if on else 'MUTED'}"

    #NEW-----------------------------------------------

    def open_dataset_panel(self):
        self.dataset_panel = DatasetPanel(
            self.screen, self.font_lg, self.font_md, self.font_sm, self.font_xs
        )

    def export_pdf(self):
        if not self.routes or not self.depot:
            self.status = "Solve first before exporting."
            return
        # reload addresses each time so edits to the file are picked up
        self.addresses = load_addresses(ADDRESSES_FILE)
        ok, result = export_solution_pdf(self.routes, self.depot, self.addresses)
        if ok:
            self.status = f"PDF saved → {result}"
        else:
            self.status = f"PDF error: {result}"

    # ── Main loop ──────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False

                # demand editor intercepts all events when open
                if self.demand_screen is not None:
                    self.demand_screen.handle(ev)
                    if self.demand_screen.cancelled:
                        self.demand_screen = None
                        self.status = "Solve cancelled."
                    elif self.demand_screen.done:
                        self._run_ga_after_demands()
                    continue

                # ── NEW dataset panel ──────────────────────────────────────────────
                if self.dataset_panel is not None:
                    self.dataset_panel.handle(ev)
                    res = self.dataset_panel.result()
                    if res == "cancel":
                        self.dataset_panel = None
                        self.status = "Dataset load cancelled."
                    elif res != "pending":
                        depot_d, customers_d, err = res
                        self.dataset_panel = None
                        if err:
                            self.status = f"Load error: {err}"
                        else:
                            self._inject_dataset(depot_d, customers_d)
                    continue  # ← keep this so other widgets are skipped

                # widgets
                self.spin_vehicles.handle(ev)
                self.spin_capacity.handle(ev)
                self.spin_gen.handle(ev)
                self.spin_pop.handle(ev)
                self.spin_rand_count.handle(ev)
                self.slider.handle(ev)

                # buttons
                if self.btn_depot.clicked(ev):
                    self.placing_depot = True
                    self.status = "Click canvas to place depot."
                if self.btn_rand_all.clicked(ev): self.randomize_all()
                if self.btn_solve.clicked(ev):    self.solve()
                if self.btn_clear.clicked(ev):    self.clear()

                #NEW------------------------
                if self.btn_dataset.clicked(ev): self.open_dataset_panel()
                if self.btn_export.clicked(ev):  self.export_pdf()

                # canvas mouse
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    if self.canvas_rect().collidepoint(mx, my):
                        self._handle_canvas_click(mx, my, ev.button)

                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    self.dragging_node = None

                if ev.type == pygame.MOUSEMOTION and self.dragging_node and not self.animating:
                    mx2, my2 = ev.pos
                    self.dragging_node.x = mx2 + self.drag_offset[0]
                    self.dragging_node.y = my2 + self.drag_offset[1]
                    self.routes = []
                    self.trucks = []
                    self.status = "Node moved — re-solve."

                if ev.type == pygame.KEYDOWN:
                    self._handle_keydown(ev)

            self.update_animation(dt)

            # render
            self.screen.fill(BG)
            if self.demand_screen is not None:
                self.demand_screen.draw()
            else:
                self.draw_grid(self.screen)
                pygame.draw.rect(self.screen, BORDER,
                                 pygame.Rect(CANVAS_X, 0, CANVAS_W, GRAPH_Y), 2, border_radius=3)
                self.draw_routes_static(self.screen)
                self.draw_trails(self.screen)
                self.draw_nodes(self.screen)
                self.draw_trucks(self.screen)
                pygame.draw.line(self.screen, BORDER, (CANVAS_X, GRAPH_Y), (W, GRAPH_Y), 2)
                self.fitness_graph.draw(self.screen)
                self.draw_panel(self.screen)
                self.draw_cursor_hint(self.screen)

            #NEW----------------------
            if self.dataset_panel is not None:
                self.dataset_panel.draw()

            pygame.display.flip()

        pygame.quit()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    VRPApp().run()

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
from dataset_loader import DatasetPanel, load_addresses, ADDRESSES_FILE
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

    # ── Init ───────────────────────────────────────────────────────────────────

    def __init__(self):
        pygame.init()
        # The real OS window is resizable like any normal application.
        # Internally we still render everything onto a fixed W x H surface
        # (so none of the existing layout/click math has to change), then
        # that surface is scaled to fit whatever size the user resizes the
        # window to, letterboxed to preserve aspect ratio.
        self.window = pygame.display.set_mode((W, H), pygame.RESIZABLE)
        self.screen = pygame.Surface((W, H))   # fixed-resolution canvas
        pygame.display.set_caption("PAC-VRP Solver")

        self._win_size   = (W, H)
        self._render_rect = pygame.Rect(0, 0, W, H)
        self._scale       = 1.0
        self._update_render_rect()

        # Every widget in this codebase calls pygame.mouse.get_pos() directly
        # for hover highlighting. Since the real OS window can now be any
        # size, we transparently patch get_pos() so it always returns
        # coordinates in the fixed internal W x H canvas space — this means
        # none of the existing widget/button code needs to change.
        self._real_get_pos = pygame.mouse.get_pos
        pygame.mouse.get_pos = lambda: self._win_to_canvas(self._real_get_pos())

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
        self.dataset_panel:  Optional[DatasetPanel] = None
        self.addresses: dict = {}
        self._block_message: Optional[str] = None

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
        BH = 30
        GAP = 4
        y  = 80

        self._stats_y = y
        y += 4 * 18 + 4
        self._sep   = []
        self._lbl_y = {}

        self._sep.append(y); y += GAP
        self._lbl_y['vehicles'] = y; y += 14
        self.spin_vehicles = Spinbox((px, y, pw, BH), 3, 1, 8, self.font_sm, editable=False); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['capacity'] = y; y += 14
        self.spin_capacity = Spinbox((px, y, pw, BH), 10, 1, 999, self.font_sm); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['gens'] = y; y += 14
        self.spin_gen = Spinbox((px, y, pw, BH), 200, 20, 500, self.font_xs); y += BH + GAP
        self._lbl_y['pop'] = y; y += 14
        self.spin_pop = Spinbox((px, y, pw, BH), 50, 20, 300, self.font_xs); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['rand_count'] = y; y += 14
        self.spin_rand_count = Spinbox((px, y, pw, BH), 15, 3, 50, self.font_xs); y += BH + GAP

        self._sep.append(y); y += GAP
        self._lbl_y['speed'] = y; y += 14
        self.slider = Slider((px, y + 14, pw, 12), 30, 500, 150.0, self.font_xs, "Speed px/s")
        y += 14 + 12 + GAP + 2

        self._sep.append(y); y += GAP
        self._lbl_y['actions'] = y; y += 14
        hw = (pw - 4) // 2
        self.btn_depot    = Button((px,      y, hw, BH), "DEPOT",  BTN_BG,    BTN_HOV,    self.font_xs)
        self.btn_rand_all = Button((px+hw+4, y, hw, BH), "RANDOM", BTN_RAND,  BTN_RAND_H, self.font_xs)
        y += BH + GAP
        self.btn_solve = Button((px,      y, hw, BH), "SOLVE", BTN_SOLVE, BTN_SOLVE_H, self.font_xs)
        self.btn_clear = Button((px+hw+4, y, hw, BH), "CLEAR", BTN_CLR,  BTN_CLR_H,  self.font_xs)
        y += BH + GAP + 2

        self._sep.append(y); y += GAP
        self._lbl_y['dataset'] = y; y += 14
        self.btn_dataset = Button((px, y, pw, BH), "ADD DATASET", BTN_RAND, BTN_RAND_H, self.font_xs)
        y += BH + GAP
        self.btn_export = Button((px, y, pw, BH), "EXTRACT PDF", BTN_SOLVE, BTN_SOLVE_H, self.font_xs)
        y += BH + GAP + 2

        self._sep.append(y); y += GAP
        self._routes_y = y

    # ── Canvas helpers ─────────────────────────────────────────────────────────

    def canvas_rect(self):
        return pygame.Rect(CANVAS_X, 0, CANVAS_W, GRAPH_Y)

    # ── Resizable-window support ───────────────────────────────────────────────
    # Internally everything is drawn onto a fixed W x H surface (self.screen).
    # That surface is then scaled to fit the real, resizable OS window,
    # preserving aspect ratio with letterboxing. These helpers translate
    # between "real window pixel" space and "internal canvas" space.

    def _update_render_rect(self):
        ww, wh = self._win_size
        scale  = min(ww / W, wh / H)
        scale  = max(scale, 0.1)
        rw, rh = int(W * scale), int(H * scale)
        rx, ry = (ww - rw) // 2, (wh - rh) // 2
        self._scale = scale
        self._render_rect = pygame.Rect(rx, ry, rw, rh)

    def _win_to_canvas(self, pos):
        """Map a real-window pixel position to internal W x H canvas space."""
        wx, wy = pos
        rr = self._render_rect
        if rr.width <= 0 or rr.height <= 0:
            return (wx, wy)
        cx = (wx - rr.x) / self._scale
        cy = (wy - rr.y) / self._scale
        return (int(cx), int(cy))

    def _present(self):
        """Scale the fixed-size internal canvas onto the real, resizable window."""
        self.window.fill((0, 0, 0))
        if self._render_rect.size == (W, H):
            scaled = self.screen
        else:
            scaled = pygame.transform.smoothscale(
                self.screen, self._render_rect.size
            )
        self.window.blit(scaled, self._render_rect.topleft)
        pygame.display.flip()

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
        self.addresses = {}

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
        self.addresses       = {}
        self.status          = "Canvas cleared."
        self.sound.play("clear")

    # ── Dataset / PDF export ───────────────────────────────────────────────────

    def open_dataset_panel(self):
        self.dataset_panel = DatasetPanel(
            self.screen, self.font_lg, self.font_md, self.font_sm, self.font_xs
        )
        print(f"[dataset] Panel opened. Files found: {self.dataset_panel._files}")

    def _inject_dataset(self, depot_d: dict, customers_d: list):
        """Convert loaded dataset dicts into Node objects, scaled to the canvas."""
        mg  = 60
        cx0, cx1 = CANVAS_X + mg, W - mg
        cy0, cy1 = mg, GRAPH_Y - mg
        cw, ch   = cx1 - cx0, cy1 - cy0

        all_x = [depot_d["x"]] + [c["x"] for c in customers_d]
        all_y = [depot_d["y"]] + [c["y"] for c in customers_d]
        rx0, rx1 = min(all_x), max(all_x)
        ry0, ry1 = min(all_y), max(all_y)
        rw = max(rx1 - rx0, 1e-9)
        rh = max(ry1 - ry0, 1e-9)

        def scale(x, y):
            sx = cx0 + (x - rx0) / rw * cw
            sy = cy0 + (y - ry0) / rh * ch
            return sx, sy

        self.customers.clear()
        self.routes.clear()
        self.trucks.clear()
        self.node_ctr        = 0
        self.fitness_history = []
        self.fitness_graph.reset()
        self.animating = False
        self.paused    = False
        self.addresses = {}   # rebuilt below from this dataset

        dx, dy     = scale(depot_d["x"], depot_d["y"])
        self.depot = Node(dx, dy, -1)

        for c in customers_d:
            sx, sy = scale(c["x"], c["y"])
            idx = self.node_ctr
            self.customers.append(Node(sx, sy, idx, demand=c["demand"]))
            addr = c.get("address", "")
            if addr:
                # keyed by the node's assigned idx (matches how
                # solution_exporter looks addresses up: f"C{node.idx}")
                self.addresses[f"C{idx}"] = addr
            self.node_ctr += 1

        # Fallback: if the dataset file had no Address column at all, try
        # the legacy separate addresses.xlsx (matched by original Customer_ID
        # from the file, e.g. "C1", "C2"...).
        if not self.addresses:
            legacy = load_addresses(ADDRESSES_FILE)
            if legacy:
                for i, c in enumerate(customers_d):
                    orig_id = c.get("id", "")
                    if orig_id in legacy:
                        self.addresses[f"C{i}"] = legacy[orig_id]

        self._rebuild_demands()
        self.sound.play("randomize")
        n_addr = len(self.addresses)
        self.status = (f"Loaded {len(self.customers)} customers "
                       f"({n_addr} with addresses). Press SOLVE.")
        print(f"[dataset] Loaded depot + {len(self.customers)} customers, "
              f"{n_addr} addresses. Press SOLVE.")

    def export_pdf(self):
        if not self.routes or not self.depot:
            self.status = "Cannot export: click SOLVE first, no routes yet!"
            self._block_message = self.status
            print("[export] Blocked: no routes/depot yet. Solve first.")
            return
        # self.addresses was already populated when the dataset was loaded
        # (either from the dataset file's own Address column, or the
        # legacy addresses.xlsx fallback). No need to reload here.

        try:
            ok, result = export_solution_pdf(self.routes, self.depot, self.addresses)
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, result = False, str(e)

        if ok:
            self.status = f"PDF saved: {result}"
            self._block_message = f"PDF saved successfully:\n{result}"
            print(f"[export] PDF saved to: {result}")
        else:
            self.status = f"PDF error: {result}"
            self._block_message = f"PDF export failed:\n{result}"
            print(f"[export] ERROR: {result}")

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
            print(f"[solve] BLOCKED: capacity {self.v_capacity} < max single demand {max_single}")
            self._block_message = self.status
            return

        min_v = math.ceil(total_d / self.v_capacity)
        if n_vehicles < min_v:
            self.status = (f"BLOCKED: {n_vehicles} truck(s) not enough. "
                           f"Need >={min_v} (demand {total_d} / cap {self.v_capacity}). "
                           f"Raise VEHICLES.")
            print(f"[solve] BLOCKED: {n_vehicles} vehicles < required {min_v} "
                  f"(total demand {total_d} / capacity {self.v_capacity})")
            self._block_message = self.status
            return

        self._block_message = None

        self.status = "Running GA...  please wait."
        self.screen.fill(BG)
        self.draw_panel(self.screen)
        self._present()
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
            y += 18

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
        surf.blit(self.font_xs.render("DATASET / EXPORT", True, TEXT_SEC), (10, self._lbl_y['dataset']))
        self.btn_dataset.draw(surf)
        self.btn_export.draw(surf)

        # route list — starts right after the last button (computed in
        # _init_widgets), not a hardcoded offset, so it can never overlap
        # the buttons above it no matter how tall the panel grows.
        route_top   = self._routes_y
        status_top  = H - 42                 # status bar starts here
        avail_h     = max(0, status_top - route_top - 24)  # room for entries
        row_h       = 22
        max_rows    = max(0, avail_h // row_h)

        pygame.draw.line(surf, BORDER, (8, route_top), (PANEL_W - 8, route_top), 1)
        surf.blit(self.font_xs.render("ROUTES  (km)", True, TEXT_SEC), (10, route_top + 4))
        if self.routes and self.depot:
            shown = self.routes[:max_rows]
            for i, r in enumerate(shown):
                col = VEHICLE_COLORS[r.vehicle_id % len(VEHICLE_COLORS)]
                ry  = route_top + 20 + i * row_h
                pygame.draw.circle(surf, col, (18, ry + 7), 5)
                tk         = next((t for t in self.trucks if t.route.vehicle_id == r.vehicle_id), None)
                done_mark  = "✓" if tk and tk.done else " "
                km         = route_km(self.depot, r)
                total_d    = sum(n.demand for n in r.nodes)
                txt        = f"V{r.vehicle_id+1} {done_mark}  {len(r.nodes)}stops  {km:.2f}km  d:{total_d}"
                info       = self.font_xs.render(txt, True, col if (tk and tk.done) else TEXT_PRI)
                surf.blit(info, (28, ry))
            if len(self.routes) > max_rows:
                more = len(self.routes) - max_rows
                ry   = route_top + 20 + max_rows * row_h
                mt   = self.font_xs.render(f"+ {more} more (see PDF)", True, TEXT_SEC)
                surf.blit(mt, (10, ry))
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

    def draw_block_popup(self, surf):
        """Big, impossible-to-miss popup for blocked actions, errors, or successes."""
        msg = self._block_message or ""
        is_success = msg.lower().startswith("pdf saved")
        accent = (90, 220, 110) if is_success else (220, 60, 60)
        bg     = (5, 35, 10)     if is_success else (40, 5, 5)
        title_txt = "SUCCESS" if is_success else "ATTENTION"

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surf.blit(dim, (0, 0))

        pw, ph = 560, 200
        px = (W - pw) // 2
        py = (H - ph) // 2
        box = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surf, bg, box, border_radius=10)
        pygame.draw.rect(surf, accent, box, 2, border_radius=10)

        title = self.font_md.render(title_txt, True, accent)
        surf.blit(title, title.get_rect(centerx=W // 2, y=py + 16))

        words = msg.split()
        lines, ln = [], ""
        for w in words:
            t = (ln + " " + w).strip()
            if self.font_sm.size(t)[0] > pw - 60:
                lines.append(ln); ln = w
            else:
                ln = t
        if ln:
            lines.append(ln)
        for i, l in enumerate(lines):
            t = self.font_sm.render(l, True, TEXT_PRI)
            surf.blit(t, t.get_rect(centerx=W // 2, y=py + 56 + i * 22))

        ok_btn = pygame.Rect(W // 2 - 60, py + ph - 50, 120, 36)
        hov = pygame.mouse.get_pos()
        c = (60, 60, 60) if not ok_btn.collidepoint(hov) else (90, 90, 90)
        pygame.draw.rect(surf, c, ok_btn, border_radius=6)
        pygame.draw.rect(surf, BORDER, ok_btn, 1, border_radius=6)
        ok_t = self.font_sm.render("OK", True, TEXT_PRI)
        surf.blit(ok_t, ok_t.get_rect(center=ok_btn.center))
        self._block_ok_btn = ok_btn

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

    def _any_spinbox_editing(self) -> bool:
        return any(
            getattr(sb, "_editing", False)
            for sb in (self.spin_vehicles, self.spin_capacity, self.spin_gen,
                       self.spin_pop, self.spin_rand_count)
        )

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

    # ── Main loop ──────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False

                if ev.type == pygame.VIDEORESIZE:
                    self._win_size = (ev.w, ev.h)
                    self.window = pygame.display.set_mode(
                        (ev.w, ev.h), pygame.RESIZABLE
                    )
                    self._update_render_rect()
                    continue

                # Remap mouse-event coordinates from real window space into
                # the fixed W x H internal canvas space, so every existing
                # click handler (written in 1200x850 coordinates) keeps
                # working unmodified no matter how the user resizes the
                # window.
                if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                               pygame.MOUSEMOTION):
                    ev.pos = self._win_to_canvas(ev.pos)

                # blocking popup intercepts all events until dismissed
                if self._block_message is not None:
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        ok_btn = getattr(self, "_block_ok_btn", None)
                        if ok_btn is not None and ok_btn.collidepoint(ev.pos):
                            self._block_message = None
                    elif ev.type == pygame.KEYDOWN and ev.key in (
                        pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_KP_ENTER
                    ):
                        self._block_message = None
                    continue

                # demand editor intercepts all events when open
                if self.demand_screen is not None:
                    self.demand_screen.handle(ev)
                    if self.demand_screen.cancelled:
                        self.demand_screen = None
                        self.status = "Solve cancelled."
                    elif self.demand_screen.done:
                        self._run_ga_after_demands()
                    continue

                # dataset panel intercepts all events when open
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
                            print(f"[dataset] Load FAILED: {err}")
                        else:
                            self._inject_dataset(depot_d, customers_d)
                    continue

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
                if self.btn_dataset.clicked(ev):  self.open_dataset_panel()
                if self.btn_export.clicked(ev):   self.export_pdf()

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

                if ev.type == pygame.KEYDOWN and not self._any_spinbox_editing():
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

            if self.dataset_panel is not None:
                self.dataset_panel.draw()

            if self._block_message and self.demand_screen is None and self.dataset_panel is None:
                self.draw_block_popup(self.screen)

            self._present()

        pygame.quit()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    VRPApp().run()

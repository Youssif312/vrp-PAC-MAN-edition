"""
app_integration.py
==================
This file documents exactly what to ADD to app.py to wire up the two new
features (Dataset Loader + Extract Solution PDF).

Do NOT run this file directly — it is a reference / patch guide.
Follow the five steps below, or copy-paste the snippets into app.py.

─────────────────────────────────────────────────────────────────────────────
STEP 1 – Add imports at the top of app.py  (after the existing imports)
─────────────────────────────────────────────────────────────────────────────

from dataset_loader   import DatasetPanel, load_addresses, ADDRESSES_FILE
from solution_exporter import export_solution_pdf

─────────────────────────────────────────────────────────────────────────────
STEP 2 – Add two instance variables inside VRPApp.__init__,
          after the line  self.demand_screen = None
─────────────────────────────────────────────────────────────────────────────

        self.dataset_panel:  Optional[DatasetPanel] = None
        self.addresses: dict = {}                    # loaded from addresses.xlsx

─────────────────────────────────────────────────────────────────────────────
STEP 3 – Add two new buttons inside _init_widgets,
          AFTER the four existing buttons (btn_solve / btn_clear block),
          i.e. after the line:  y += BH + GAP + 4
─────────────────────────────────────────────────────────────────────────────

        self._sep.append(y); y += GAP
        self._lbl_y['dataset'] = y; y += 16
        self.btn_dataset = Button(
            (px, y, pw, BH), "ADD DATASET", BTN_RAND, BTN_RAND_H, self.font_xs
        ); y += BH + GAP
        self.btn_export = Button(
            (px, y, pw, BH), "EXTRACT PDF", BTN_SOLVE, BTN_SOLVE_H, self.font_xs
        ); y += BH + GAP + 4

─────────────────────────────────────────────────────────────────────────────
STEP 4 – Add two handler methods to VRPApp  (anywhere before run())
─────────────────────────────────────────────────────────────────────────────

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

─────────────────────────────────────────────────────────────────────────────
STEP 5 – Add event handling inside run()
─────────────────────────────────────────────────────────────────────────────

Inside the  for ev in pygame.event.get():  loop, RIGHT AFTER the block that
handles  self.demand_screen  (the `if self.demand_screen is not None:` block),
add:

            # ── dataset panel ──────────────────────────────────────────────
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
                continue           # ← keep this so other widgets are skipped

Then add the two button click handlers in the same loop, alongside the other
btn_xxx.clicked(ev) lines:

                if self.btn_dataset.clicked(ev): self.open_dataset_panel()
                if self.btn_export.clicked(ev):  self.export_pdf()

─────────────────────────────────────────────────────────────────────────────
STEP 6 – Add _inject_dataset method to VRPApp
─────────────────────────────────────────────────────────────────────────────

    def _inject_dataset(self, depot_d: dict, customers_d: list):
        \"\"\"
        Convert dicts from load_dataset() into Node objects and inject them
        into the app.  Coordinates are scaled to fit the canvas.
        \"\"\"
        import math
        from nodes import Node

        # canvas bounds
        mg  = 60
        cx0 = CANVAS_X + mg;  cx1 = W - mg
        cy0 = mg;              cy1 = GRAPH_Y - mg
        cw  = cx1 - cx0;      ch  = cy1 - cy0

        # find bounding box of raw data
        all_x = [depot_d["x"]] + [c["x"] for c in customers_d]
        all_y = [depot_d["y"]] + [c["y"] for c in customers_d]
        rx0, rx1 = min(all_x), max(all_x)
        ry0, ry1 = min(all_y), max(all_y)
        rw = max(rx1 - rx0, 1);  rh = max(ry1 - ry0, 1)

        def scale(x, y):
            sx = cx0 + (x - rx0) / rw * cw
            sy = cy0 + (y - ry0) / rh * ch
            return sx, sy

        # reset everything
        self.customers.clear()
        self.routes.clear()
        self.trucks.clear()
        self.node_ctr        = 0
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

─────────────────────────────────────────────────────────────────────────────
STEP 7 – Draw the new buttons in draw_panel  (and the overlay in run())
─────────────────────────────────────────────────────────────────────────────

In draw_panel(), after  self.btn_clear.draw(surf)  add:

        surf.blit(self.font_xs.render("DATASET / EXPORT", True, TEXT_SEC),
                  (10, self._lbl_y['dataset']))
        self.btn_dataset.draw(surf)
        self.btn_export.draw(surf)

In the rendering section at the bottom of run(), after
    self.draw_cursor_hint(self.screen)
add:

            if self.dataset_panel is not None:
                self.dataset_panel.draw()

─────────────────────────────────────────────────────────────────────────────
ADDRESSES FILE FORMAT  (addresses.xlsx)
─────────────────────────────────────────────────────────────────────────────

Create an Excel file with two columns:

    Customer_ID | Address
    C1          | 123 Main Street, Cairo
    C2          | 45 Tahrir Square, Cairo
    …

Place it in the same folder as app.py (or change ADDRESSES_FILE in
dataset_loader.py to point anywhere you like).

─────────────────────────────────────────────────────────────────────────────
DATASET FILE FORMAT  (any name, inside the datasets/ folder)
─────────────────────────────────────────────────────────────────────────────

    Customer_ID | X_Coord | Y_Coord | Demand
    Depot       |  50     |  50     |  0
    C1          |  51     |  25     |  9
    C2          |  92     |  88     |  5
    …

The first row whose Customer_ID is "Depot" (case-insensitive) becomes the
depot node.  All other rows become customers.
"""

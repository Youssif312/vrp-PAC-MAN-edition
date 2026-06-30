"""
dataset_loader.py
-----------------
Standalone module that adds two things to the VRP app:

1. DatasetPanel  – a pygame overlay that lets the user:
     • pick a DATASETS_DIR folder (scanned on demand with Refresh)
     • pick one .xlsx dataset file from the list
     • click Load → returns depot + customer nodes ready for the app

2. load_dataset(path)  – reads an .xlsx with columns:
       Customer_ID | X_Coord | Y_Coord | Demand | Address
   The row whose Customer_ID is "Depot" (case-insensitive) becomes the depot.
   All other rows become customers. The Address column is optional but, if
   present, addresses are read directly from this same file — no separate
   address book file is needed.

Drop this file next to app.py. The datasets folder is configured by the
constant below.
"""

import os
import math
import pygame
import pandas as pd

# ── Configuration ──────────────────────────────────────────────────────────────
# Folder that is scanned for *.xlsx dataset files.
# Change this to whatever folder you keep your datasets in.
DATASETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")

# ── Colours (match the app palette) ───────────────────────────────────────────
_BG        = (  0,   0,   0)
_OVERLAY   = (  0,   0,  18)
_PANEL     = (  5,   5,  40)
_BORDER    = ( 33,  33, 200)
_TEXT_PRI  = (255, 255,   0)
_TEXT_SEC  = (200, 160, 255)
_ACCENT    = ( 33, 200, 200)
_BTN_BG    = (  5,   5,  55)
_BTN_HOV   = ( 33,  33, 120)
_BTN_OK    = (  0, 160,   0)
_BTN_OK_H  = (  0, 210,   0)
_BTN_REF   = ( 80,  80,   0)
_BTN_REF_H = (140, 140,   0)
_BTN_CAN   = (160,   0,   0)
_BTN_CAN_H = (220,  40,  40)
_SEL_BG    = ( 18,  18,  80)
_HOV_BG    = ( 10,  10,  55)


# ── Data loading helpers ───────────────────────────────────────────────────────

def load_dataset(path: str):
    """
    Read a VRP dataset Excel file.

    Required columns (case-insensitive):
        Customer_ID | X_Coord | Y_Coord | Demand

    Optional column:
        Address     – addresses are read directly from this same file.

    Returns:
        depot     – dict  {x, y}                              (None if missing)
        customers – list of dicts [{id, x, y, demand, address}, ...]
        error     – str or None
    """
    try:
        df = pd.read_excel(path)
        df.columns = [c.strip() for c in df.columns]

        # normalise column names to lower
        col_map = {c.lower(): c for c in df.columns}
        needed  = ["customer_id", "x_coord", "y_coord", "demand"]
        for n in needed:
            if n not in col_map:
                return None, [], f"Missing column: {n}"

        id_col   = col_map["customer_id"]
        x_col    = col_map["x_coord"]
        y_col    = col_map["y_coord"]
        d_col    = col_map["demand"]
        addr_col = col_map.get("address")   # optional

        depot     = None
        customers = []

        for _, row in df.iterrows():
            cid = str(row[id_col]).strip()
            try:
                x = float(row[x_col])
                y = float(row[y_col])
                d = int(row[d_col])
            except (ValueError, TypeError):
                continue

            addr = ""
            if addr_col is not None:
                raw = row[addr_col]
                if pd.notna(raw):
                    addr = str(raw).strip()

            if cid.lower() == "depot":
                depot = {"x": x, "y": y, "address": addr}
            else:
                customers.append({"id": cid, "x": x, "y": y, "demand": d, "address": addr})

        if depot is None:
            return None, [], "No 'Depot' row found in dataset."
        return depot, customers, None

    except Exception as e:
        return None, [], str(e)


def scan_datasets(folder: str = None) -> list:
    """Return sorted list of .xlsx filenames in DATASETS_DIR."""
    if folder is None:
        folder = DATASETS_DIR
    if not os.path.isdir(folder):
        return []
    return sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith(".xlsx")
    )


# ── Pygame overlay panel ───────────────────────────────────────────────────────

class DatasetPanel:
    """
    Full-screen overlay that lets the user pick a dataset file.

    Usage (inside VRPApp.run()):
        if self.dataset_panel is not None:
            self.dataset_panel.handle(ev)
            result = self.dataset_panel.result()
            if result == "cancel":
                self.dataset_panel = None
            elif result is not None:          # (depot, customers, error)
                self.dataset_panel = None
                depot, customers, err = result
                if err:
                    self.status = f"Load error: {err}"
                else:
                    # inject into app …
    """

    _W = 700
    _H = 520

    def __init__(self, screen, font_lg, font_md, font_sm, font_xs):
        self.screen   = screen
        self.f_lg     = font_lg
        self.f_md     = font_md
        self.f_sm     = font_sm
        self.f_xs     = font_xs
        self._files   = []
        self._sel     = -1
        self._scroll  = 0
        self._error   = ""
        self._result  = "pending"   # "pending" | "cancel" | (depot, customers, err)
        self._refresh()

        sw, sh = screen.get_size()
        self._ox = (sw - self._W) // 2
        self._oy = (sh - self._H) // 2

    # ── geometry ───────────────────────────────────────────────────────────────

    def _r(self, x, y, w, h):
        return pygame.Rect(self._ox + x, self._oy + y, w, h)

    def _list_rect(self):
        return self._r(20, 90, self._W - 40, self._H - 180)

    def _btn_refresh(self): return self._r(20,          self._H - 70, 140, 36)
    def _btn_load(self):    return self._r(self._W//2 - 75, self._H - 70, 150, 36)
    def _btn_cancel(self):  return self._r(self._W - 160,   self._H - 70, 140, 36)

    # ── internal helpers ───────────────────────────────────────────────────────

    def _refresh(self):
        self._files  = scan_datasets()
        self._sel    = 0 if self._files else -1
        self._scroll = 0
        self._error  = "" if self._files else f"No .xlsx files found in:\n{DATASETS_DIR}"

    def _max_vis(self) -> int:
        return (self._list_rect().height - 4) // 34

    def _vis_range(self):
        mv = self._max_vis()
        return range(self._scroll, min(self._scroll + mv, len(self._files)))

    def result(self):
        """Returns "pending" while open, "cancel" on cancel, or (depot, customers, err)."""
        return self._result

    # ── event handling ─────────────────────────────────────────────────────────

    def handle(self, ev):
        if self._result != "pending":
            return
        hov = pygame.mouse.get_pos()

        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self._result = "cancel"
                return
            if ev.key == pygame.K_UP   and self._sel > 0:
                self._sel -= 1
                self._clamp_scroll()
            if ev.key == pygame.K_DOWN and self._sel < len(self._files) - 1:
                self._sel += 1
                self._clamp_scroll()
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._do_load()

        if ev.type == pygame.MOUSEWHEEL:
            mx = max(0, len(self._files) - self._max_vis())
            self._scroll = max(0, min(mx, self._scroll - ev.y))

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            mx, my = ev.pos
            if self._btn_cancel().collidepoint(mx, my):
                self._result = "cancel"
                return
            if self._btn_refresh().collidepoint(mx, my):
                self._refresh()
                return
            if self._btn_load().collidepoint(mx, my):
                self._do_load()
                return
            lr = self._list_rect()
            if lr.collidepoint(mx, my):
                row = (my - lr.y - 4) // 34
                idx = self._scroll + row
                if 0 <= idx < len(self._files):
                    self._sel = idx
                    self._error = ""

    def _clamp_scroll(self):
        mv = self._max_vis()
        if self._sel < self._scroll:
            self._scroll = self._sel
        if self._sel >= self._scroll + mv:
            self._scroll = self._sel - mv + 1

    def _do_load(self):
        if self._sel < 0 or self._sel >= len(self._files):
            self._error = "Select a file first."
            return
        path = os.path.join(DATASETS_DIR, self._files[self._sel])
        depot, customers, err = load_dataset(path)
        self._result = (depot, customers, err)

    # ── drawing ────────────────────────────────────────────────────────────────

    def draw(self):
        # dim background
        dim = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        self.screen.blit(dim, (0, 0))

        # panel
        panel = pygame.Rect(self._ox, self._oy, self._W, self._H)
        pygame.draw.rect(self.screen, _PANEL,  panel, border_radius=10)
        pygame.draw.rect(self.screen, _BORDER, panel, 2,  border_radius=10)

        # title
        t = self.f_lg.render("ADD FROM DATASET", True, _TEXT_PRI)
        self.screen.blit(t, t.get_rect(centerx=self._ox + self._W // 2, y=self._oy + 14))

        # sub-label
        sub = self.f_xs.render(
            f"Folder: {DATASETS_DIR}", True, _TEXT_SEC
        )
        self.screen.blit(sub, (self._ox + 20, self._oy + 50))
        pygame.draw.line(self.screen, _BORDER,
                         (self._ox + 20, self._oy + 72),
                         (self._ox + self._W - 20, self._oy + 72), 1)

        # file list
        lr  = self._list_rect()
        pygame.draw.rect(self.screen, (2, 2, 20), lr, border_radius=6)
        pygame.draw.rect(self.screen, _BORDER,    lr, 1, border_radius=6)
        hov = pygame.mouse.get_pos()

        if not self._files:
            msg = self.f_xs.render(self._error or "No datasets found.", True, _TEXT_SEC)
            self.screen.blit(msg, msg.get_rect(center=lr.center))
        else:
            for li, fi in enumerate(self._vis_range()):
                ry  = lr.y + 4 + li * 34
                row = pygame.Rect(lr.x + 2, ry, lr.width - 4, 30)
                sel = (fi == self._sel)
                if sel:
                    pygame.draw.rect(self.screen, _SEL_BG, row, border_radius=4)
                    pygame.draw.rect(self.screen, _BORDER, row, 1, border_radius=4)
                elif row.collidepoint(hov):
                    pygame.draw.rect(self.screen, _HOV_BG, row, border_radius=4)
                icon_col = _ACCENT if sel else _TEXT_SEC
                self.screen.blit(
                    self.f_xs.render("▶ " + self._files[fi], True, icon_col),
                    (row.x + 10, row.y + 8),
                )

            # scroll indicator
            total = len(self._files)
            mv    = self._max_vis()
            if total > mv:
                si = self.f_xs.render(
                    f"{self._scroll+1}–{min(self._scroll+mv, total)} of {total}",
                    True, _TEXT_SEC,
                )
                self.screen.blit(si, si.get_rect(
                    centerx=self._ox + self._W // 2,
                    y=lr.bottom + 4,
                ))

        # error message
        if self._error:
            em = self.f_xs.render(self._error, True, (255, 80, 80))
            self.screen.blit(em, em.get_rect(
                centerx=self._ox + self._W // 2, y=self._oy + self._H - 100
            ))

        # buttons
        self._draw_btn(self._btn_refresh(), "⟳  REFRESH",  _BTN_REF,  _BTN_REF_H)
        self._draw_btn(self._btn_load(),    "  LOAD  ",   _BTN_OK,   _BTN_OK_H)
        self._draw_btn(self._btn_cancel(),  "CANCEL",      _BTN_CAN,  _BTN_CAN_H)

    def _draw_btn(self, rect, label, col, hov_col):
        c = hov_col if rect.collidepoint(pygame.mouse.get_pos()) else col
        pygame.draw.rect(self.screen, c,       rect, border_radius=6)
        pygame.draw.rect(self.screen, _BORDER, rect, 1, border_radius=6)
        t = self.f_md.render(label, True, _TEXT_PRI)
        self.screen.blit(t, t.get_rect(center=rect.center))

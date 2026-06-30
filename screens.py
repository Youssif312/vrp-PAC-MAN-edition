import math
import pygame

from constants import (
    W, H, BORDER, TEXT_PRI, TEXT_SEC, ACCENT,
    BTN_BG, BTN_HOV, BTN_SOLVE, BTN_SOLVE_H, BTN_CLR, BTN_CLR_H,
    VEHICLE_COLORS, GRAPH_BG, GRAPH_BEST, GRAPH_AVG, GRAPH_GRID,
)


# ── Demand editor ──────────────────────────────────────────────────────────────

class DemandInputScreen:
    def __init__(self, screen, customers, font_lg, font_md, font_sm, font_xs):
        self.screen    = screen
        self.customers = customers
        self.font_lg   = font_lg
        self.font_md   = font_md
        self.font_sm   = font_sm
        self.font_xs   = font_xs
        self.demands   = [c.demand for c in customers]
        self.active    = 0
        self.input_str = str(self.demands[0])
        self.done      = False
        self.cancelled = False
        self.scroll    = 0
        self._dragging_bar = False
        self._drag_offset_y = 0

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _max_vis(self) -> int:
        return min(len(self.customers), (H - 220) // 34)

    def _vis(self) -> list:
        mv = self._max_vis()
        return list(range(self.scroll, min(self.scroll + mv, len(self.customers))))

    def _commit(self):
        try:
            v = int(self.input_str)
            if v >= 1:
                self.demands[self.active] = v
        except ValueError:
            pass
        self.input_str = str(self.demands[self.active])

    def _confirm_btn(self): return pygame.Rect(W // 2 - 110, H - 65, 100, 38)
    def _cancel_btn(self):  return pygame.Rect(W // 2 +  10, H - 65, 100, 38)

    def _list_area(self):
        """Bounding box of the customer rows (used to size the scrollbar)."""
        hx = W // 2 - 170
        top = 155
        mv  = self._max_vis()
        h   = mv * 34
        return pygame.Rect(hx - 4, top - 2, 348, h)

    def _scrollbar_track(self):
        la = self._list_area()
        return pygame.Rect(la.right + 12, la.y, 14, la.height)

    def _scrollbar_thumb(self):
        track = self._scrollbar_track()
        total = len(self.customers)
        mv    = self._max_vis()
        if total <= mv:
            return None
        thumb_h = max(24, int(track.height * mv / total))
        max_scroll = total - mv
        t = self.scroll / max_scroll if max_scroll > 0 else 0
        thumb_y = track.y + int((track.height - thumb_h) * t)
        return pygame.Rect(track.x, thumb_y, track.width, thumb_h)

    def _btn_jump_end(self):
        track = self._scrollbar_track()
        return pygame.Rect(track.x - 2, track.bottom + 8, track.width + 4, 26)

    def _btn_jump_start(self):
        track = self._scrollbar_track()
        return pygame.Rect(track.x - 2, track.y - 34, track.width + 4, 26)

    def _set_scroll(self, value: int):
        mx = max(0, len(self.customers) - self._max_vis())
        self.scroll = max(0, min(mx, value))

    # ── Event handling ─────────────────────────────────────────────────────────

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_ESCAPE:
                self.cancelled = True
                return
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit()
                if self.active < len(self.customers) - 1:
                    self.active   += 1
                    self.input_str = str(self.demands[self.active])
                else:
                    self.done = True
                return
            if k == pygame.K_TAB:
                self._commit()
                self.active    = (self.active + 1) % len(self.customers)
                self.input_str = str(self.demands[self.active])
                return
            if k == pygame.K_UP:
                self._commit()
                self.active    = max(0, self.active - 1)
                self.input_str = str(self.demands[self.active])
                return
            if k == pygame.K_DOWN:
                self._commit()
                self.active    = min(len(self.customers) - 1, self.active + 1)
                self.input_str = str(self.demands[self.active])
                return
            if k == pygame.K_BACKSPACE:
                self.input_str = self.input_str[:-1]
                return
            if ev.unicode.isdigit():
                self.input_str += ev.unicode
                return

        if ev.type == pygame.MOUSEWHEEL:
            mx = max(0, len(self.customers) - self._max_vis())
            self.scroll = max(0, min(mx, self.scroll - ev.y))

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._dragging_bar = False

        if ev.type == pygame.MOUSEMOTION and self._dragging_bar:
            track = self._scrollbar_track()
            thumb = self._scrollbar_thumb()
            if thumb is not None and track.height > thumb.height:
                rel_y   = ev.pos[1] - track.y - self._drag_offset_y
                t       = rel_y / (track.height - thumb.height)
                total   = len(self.customers)
                mv      = self._max_vis()
                self._set_scroll(round(t * (total - mv)))
            return

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            mx, my = ev.pos
            if self._confirm_btn().collidepoint(mx, my):
                self._commit()
                self.done = True
                return
            if self._cancel_btn().collidepoint(mx, my):
                self.cancelled = True
                return

            # scrollbar: jump-to-start / jump-to-end shortcuts
            if len(self.customers) > self._max_vis():
                if self._btn_jump_start().collidepoint(mx, my):
                    self._set_scroll(0)
                    return
                if self._btn_jump_end().collidepoint(mx, my):
                    self._set_scroll(len(self.customers))
                    return

                thumb = self._scrollbar_thumb()
                track = self._scrollbar_track()
                if thumb is not None and thumb.collidepoint(mx, my):
                    self._dragging_bar  = True
                    self._drag_offset_y = my - thumb.y
                    return
                if track.collidepoint(mx, my):
                    # click on track (outside thumb) -> jump one page
                    mv = self._max_vis()
                    if thumb is not None and my < thumb.y:
                        self._set_scroll(self.scroll - mv)
                    else:
                        self._set_scroll(self.scroll + mv)
                    return

            for li, ci in enumerate(self._vis()):
                ry  = 155 + li * 34
                hx2 = W // 2 - 170
                mr  = pygame.Rect(hx2,       ry, 28, 28)
                pr  = pygame.Rect(hx2 + 312, ry, 28, 28)
                row = pygame.Rect(hx2,       ry, 340, 28)
                if mr.collidepoint(mx, my):
                    self._commit()
                    self.demands[ci] = max(1, self.demands[ci] - 1)
                    self.active      = ci
                    self.input_str   = str(self.demands[ci])
                    return
                if pr.collidepoint(mx, my):
                    self._commit()
                    self.demands[ci] += 1
                    self.active       = ci
                    self.input_str    = str(self.demands[ci])
                    return
                if row.collidepoint(mx, my):
                    self._commit()
                    self.active    = ci
                    self.input_str = str(self.demands[ci])
                    return

    # ── Drawing ────────────────────────────────────────────────────────────────

    def draw(self):
        s = self.screen
        s.fill((0, 0, 18))

        t = self.font_lg.render("CUSTOMER DEMANDS", True, TEXT_PRI)
        s.blit(t, t.get_rect(centerx=W // 2, y=16))
        sub = self.font_xs.render(
            "↑↓ navigate  |  type  |  ENTER next  |  scroll  |  ESC cancel",
            True, TEXT_SEC,
        )
        s.blit(sub, sub.get_rect(centerx=W // 2, y=46))
        pygame.draw.line(s, BORDER, (80, 70), (W - 80, 70), 1)

        hx = W // 2 - 170
        s.blit(self.font_xs.render("Customer", True, ACCENT), (hx + 36,  118))
        s.blit(self.font_xs.render("Demand",   True, ACCENT), (hx + 236, 118))
        pygame.draw.line(s, BORDER, (hx, 135), (hx + 340, 135), 1)

        hov = pygame.mouse.get_pos()
        for li, ci in enumerate(self._vis()):
            ry  = 155 + li * 34
            col = VEHICLE_COLORS[ci % len(VEHICLE_COLORS)]
            ia  = (ci == self.active)

            pygame.draw.rect(s,
                             (18, 18, 55) if ia else (5, 5, 28),
                             (hx - 4, ry - 2, 348, 30), border_radius=4)
            if ia:
                pygame.draw.rect(s, BORDER, (hx - 4, ry - 2, 348, 30), 1, border_radius=4)

            # minus button
            mr = pygame.Rect(hx, ry, 28, 28)
            pygame.draw.rect(s, BTN_HOV if mr.collidepoint(hov) else BTN_BG, mr, border_radius=4)
            pygame.draw.rect(s, BORDER, mr, 1, border_radius=4)
            mt = self.font_md.render("−", True, TEXT_PRI)
            s.blit(mt, mt.get_rect(center=mr.center))

            # label
            pygame.draw.circle(s, col, (hx + 40, ry + 12), 6)
            lbl = self.font_xs.render(f"Customer {ci + 1:02d}", True,
                                      TEXT_PRI if ia else TEXT_SEC)
            s.blit(lbl, (hx + 50, ry + 6))

            # value / input
            cursor  = "|" if ia and (pygame.time.get_ticks() // 500) % 2 == 0 else ""
            disp    = (self.input_str if ia else str(self.demands[ci])) + cursor
            dv      = self.font_md.render(disp, True, ACCENT if ia else TEXT_PRI)
            s.blit(dv, dv.get_rect(centerx=hx + 240, y=ry + 5))

            # plus button
            pr = pygame.Rect(hx + 312, ry, 28, 28)
            pygame.draw.rect(s, BTN_HOV if pr.collidepoint(hov) else BTN_BG, pr, border_radius=4)
            pygame.draw.rect(s, BORDER, pr, 1, border_radius=4)
            pt = self.font_md.render("+", True, TEXT_PRI)
            s.blit(pt, pt.get_rect(center=pr.center))

        # scroll indicator
        total = len(self.customers)
        mv    = self._max_vis()
        if total > mv:
            sh = self.font_xs.render(
                f"{self.scroll + 1}–{min(self.scroll + mv, total)} of {total}",
                True, TEXT_SEC,
            )
            s.blit(sh, sh.get_rect(centerx=W // 2, y=H - 100))

        # scrollbar (only if list overflows)
        if total > mv:
            track = self._scrollbar_track()
            pygame.draw.rect(s, (20, 20, 60), track, border_radius=6)
            pygame.draw.rect(s, BORDER, track, 1, border_radius=6)

            thumb = self._scrollbar_thumb()
            if thumb is not None:
                thumb_col = ACCENT if thumb.collidepoint(hov) or self._dragging_bar else (70, 70, 180)
                pygame.draw.rect(s, thumb_col, thumb, border_radius=6)
                pygame.draw.rect(s, BORDER, thumb, 1, border_radius=6)

            # jump-to-start button (▲ above track)
            jb_start = self._btn_jump_start()
            c1 = BTN_HOV if jb_start.collidepoint(hov) else BTN_BG
            pygame.draw.rect(s, c1, jb_start, border_radius=4)
            pygame.draw.rect(s, BORDER, jb_start, 1, border_radius=4)
            up = self.font_xs.render("▲", True, TEXT_PRI)
            s.blit(up, up.get_rect(center=jb_start.center))

            # jump-to-end button (▼ below track, gets you to the last
            # customers instantly so CONFIRM is one click away)
            jb_end = self._btn_jump_end()
            c2 = BTN_SOLVE_H if jb_end.collidepoint(hov) else BTN_SOLVE
            pygame.draw.rect(s, c2, jb_end, border_radius=4)
            pygame.draw.rect(s, BORDER, jb_end, 1, border_radius=4)
            dn = self.font_xs.render("▼ END", True, TEXT_PRI)
            s.blit(dn, dn.get_rect(center=jb_end.center))

        # confirm / cancel buttons
        cb  = self._confirm_btn()
        cx2 = self._cancel_btn()
        pygame.draw.rect(s, BTN_SOLVE_H if cb.collidepoint(hov) else BTN_SOLVE, cb, border_radius=6)
        pygame.draw.rect(s, BORDER, cb, 1, border_radius=6)
        ct = self.font_md.render("CONFIRM", True, TEXT_PRI)
        s.blit(ct, ct.get_rect(center=cb.center))

        pygame.draw.rect(s, BTN_CLR_H if cx2.collidepoint(hov) else BTN_CLR, cx2, border_radius=6)
        pygame.draw.rect(s, BORDER, cx2, 1, border_radius=6)
        cc = self.font_md.render("CANCEL", True, TEXT_PRI)
        s.blit(cc, cc.get_rect(center=cx2.center))


# ── Fitness graph ──────────────────────────────────────────────────────────────

class FitnessGraph:
    PAD = 8

    def __init__(self, x, y, w, h, font_sm, font_xs):
        self.rect    = pygame.Rect(x, y, w, h)
        self.fsm     = font_sm
        self.fxs     = font_xs
        self.history = []

    def reset(self):
        self.history = []

    def update(self, history: list):
        self.history = history

    def draw(self, surf):
        r = self.rect
        p = self.PAD
        pygame.draw.rect(surf, GRAPH_BG,    r, border_radius=5)
        pygame.draw.rect(surf, BORDER,      r, 1, border_radius=5)
        surf.blit(self.fsm.render("FITNESS PER GENERATION", True, TEXT_SEC), (r.x + p, r.y + 3))

        # legend
        lx, ly = r.right - 180, r.y + 3
        pygame.draw.line(surf, GRAPH_BEST, (lx,      ly + 5), (lx + 12, ly + 5), 2)
        surf.blit(self.fxs.render("Best", True, GRAPH_BEST), (lx + 15, ly))
        pygame.draw.line(surf, GRAPH_AVG,  (lx + 55, ly + 5), (lx + 67, ly + 5), 2)
        surf.blit(self.fxs.render("Avg",  True, GRAPH_AVG),  (lx + 70, ly))

        if not self.history:
            m = self.fxs.render("Run GA to see fitness curve", True, TEXT_SEC)
            surf.blit(m, m.get_rect(center=r.center))
            return

        px2 = r.x + p + 36
        py2 = r.y + 18
        pw2 = r.width  - p * 2 - 40
        ph2 = r.height - 30

        # grid lines
        for i in range(5):
            gy = py2 + int(i * ph2 / 4)
            pygame.draw.line(surf, GRAPH_GRID, (px2, gy), (px2 + pw2, gy), 1)

        n   = len(self.history)
        ab  = [h[0] for h in self.history]
        aa  = [h[1] for h in self.history]
        mx2 = max(ab)
        mn2 = min(aa)
        vr  = max(mx2 - mn2, 1e-9)

        def to_screen(gi, v):
            sx = px2 + int(gi / max(n - 1, 1) * pw2)
            sy = py2 + ph2 - int((v - mn2) / vr * ph2)
            return (sx, max(py2, min(py2 + ph2, sy)))

        if n >= 2:
            pb = [to_screen(i, v) for i, v in enumerate(ab)]
            pa = [to_screen(i, v) for i, v in enumerate(aa)]

            # shaded area under best curve
            fs = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            fp = ([(px2 - r.x, py2 + ph2 - r.y)]
                  + [(fx - r.x, fy - r.y) for fx, fy in pb]
                  + [(px2 + pw2 - r.x, py2 + ph2 - r.y)])
            pygame.draw.polygon(fs, (*GRAPH_BEST, 18), fp)
            surf.blit(fs, (r.x, r.y))

            for i in range(1, n):
                pygame.draw.line(surf, GRAPH_AVG,  pa[i - 1], pa[i], 1)
                pygame.draw.line(surf, GRAPH_BEST, pb[i - 1], pb[i], 2)

            lb = to_screen(n - 1, ab[-1])
            la = to_screen(n - 1, aa[-1])
            surf.blit(self.fxs.render(f"{ab[-1]:.4f}", True, GRAPH_BEST), (lb[0] + 3, lb[1] - 8))
            surf.blit(self.fxs.render(f"{aa[-1]:.4f}", True, GRAPH_AVG),  (la[0] + 3, la[1] + 2))

        # y-axis labels
        for i in range(5):
            gy = py2 + int(i * ph2 / 4)
            v  = mx2 - (mx2 - mn2) * i / 4
            surf.blit(self.fxs.render(f"{v:.3f}", True, TEXT_SEC), (r.x + 2, gy - 5))

        # x-axis labels
        for i in range(6):
            gx  = px2 + int(i * pw2 / 5)
            gen = int(i * (n - 1) / 5)
            lbl = self.fxs.render(str(gen), True, TEXT_SEC)
            surf.blit(lbl, (gx - lbl.get_width() // 2, py2 + ph2 + 2))

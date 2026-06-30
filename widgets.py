import math
import pygame

from constants import (
    BORDER, TEXT_PRI, TEXT_SEC, ACCENT,
    BTN_BG, BTN_HOV, PANEL_BG,
)


class Button:
    def __init__(self, rect, label, color, hover, font):
        self.rect  = pygame.Rect(rect)
        self.label = label
        self.color = color
        self.hover = hover
        self.font  = font

    def draw(self, surf):
        c = self.hover if self.rect.collidepoint(pygame.mouse.get_pos()) else self.color
        pygame.draw.rect(surf, c,      self.rect, border_radius=6)
        pygame.draw.rect(surf, BORDER, self.rect, 1, border_radius=6)
        t = self.font.render(self.label, True, TEXT_PRI)
        surf.blit(t, t.get_rect(center=self.rect.center))

    def clicked(self, ev) -> bool:
        return (ev.type == pygame.MOUSEBUTTONDOWN
                and ev.button == 1
                and self.rect.collidepoint(ev.pos))


class Spinbox:
    """
    A numeric stepper with -/+ buttons.

    If `editable=True` (default), double-clicking the value area lets you
    type a number directly instead of clicking +/- repeatedly. Press ENTER
    to confirm, ESCAPE to cancel, BACKSPACE to edit. Pass editable=False to
    disable this (used for VEHICLES, since typing a vehicle count freely
    can put the GA in a confusing state).
    """
    _BTN_W = 24
    _DOUBLE_CLICK_MS = 400

    def __init__(self, rect, value, mn, mx, font, editable=True):
        self.rect     = pygame.Rect(rect)
        self.value    = value
        self.mn       = mn
        self.mx       = mx
        self.font     = font
        self.editable = editable
        bw = self._BTN_W
        self.bd = pygame.Rect(rect[0],               rect[1], bw, rect[3])
        self.bi = pygame.Rect(rect[0] + rect[2] - bw, rect[1], bw, rect[3])

        self._editing       = False
        self._edit_str      = ""
        self._last_click_ms = -10_000
        self._last_click_pos = (-1, -1)

    @property
    def _value_rect(self):
        bw = self._BTN_W
        return pygame.Rect(self.rect.x + bw, self.rect.y,
                           self.rect.width - 2 * bw, self.rect.height)

    def draw(self, surf):
        pygame.draw.rect(surf, PANEL_BG, self.rect, border_radius=5)
        pygame.draw.rect(surf, BORDER,   self.rect, 1, border_radius=5)
        hov = pygame.mouse.get_pos()
        for btn, sym in ((self.bd, '−'), (self.bi, '+')):
            c = BTN_HOV if btn.collidepoint(hov) else BTN_BG
            pygame.draw.rect(surf, c,      btn, border_radius=4)
            pygame.draw.rect(surf, BORDER, btn, 1, border_radius=4)
            t = self.font.render(sym, True, TEXT_PRI)
            surf.blit(t, t.get_rect(center=btn.center))

        if self._editing:
            cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
            disp   = self._edit_str + cursor
            v = self.font.render(disp, True, ACCENT)
            vr = self._value_rect
            pygame.draw.rect(surf, (20, 20, 70), vr, border_radius=4)
            pygame.draw.rect(surf, ACCENT, vr, 1, border_radius=4)
        else:
            v = self.font.render(str(self.value), True, ACCENT)
        surf.blit(v, v.get_rect(center=self.rect.center))

    def _commit_edit(self):
        try:
            n = int(self._edit_str)
            self.value = max(self.mn, min(self.mx, n))
        except ValueError:
            pass
        self._editing  = False
        self._edit_str = ""

    def handle(self, ev):
        if self._editing:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._commit_edit()
                elif ev.key == pygame.K_ESCAPE:
                    self._editing  = False
                    self._edit_str = ""
                elif ev.key == pygame.K_BACKSPACE:
                    self._edit_str = self._edit_str[:-1]
                elif ev.unicode.isdigit():
                    self._edit_str += ev.unicode
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if not self._value_rect.collidepoint(ev.pos):
                    self._commit_edit()
            return

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.bd.collidepoint(ev.pos):
                self.value = max(self.mn, self.value - 1)
                return
            if self.bi.collidepoint(ev.pos):
                self.value = min(self.mx, self.value + 1)
                return

            if self.editable and self._value_rect.collidepoint(ev.pos):
                now = pygame.time.get_ticks()
                is_double = (
                    now - self._last_click_ms < self._DOUBLE_CLICK_MS
                    and math.hypot(ev.pos[0] - self._last_click_pos[0],
                                   ev.pos[1] - self._last_click_pos[1]) < 10
                )
                self._last_click_ms  = now
                self._last_click_pos = ev.pos
                if is_double:
                    self._editing  = True
                    self._edit_str = ""


class Slider:
    def __init__(self, rect, mn, mx, val, font, label):
        self.rect  = pygame.Rect(rect)
        self.mn    = mn
        self.mx    = mx
        self.value = val
        self.font  = font
        self.label = label
        self.drag  = False

    @property
    def kx(self) -> int:
        return self.rect.x + int(
            (self.value - self.mn) / (self.mx - self.mn) * self.rect.width
        )

    def draw(self, surf):
        ty = self.rect.centery
        pygame.draw.line(surf, BORDER, (self.rect.x, ty), (self.rect.right, ty), 2)
        pygame.draw.line(surf, ACCENT, (self.rect.x, ty), (self.kx,         ty), 2)
        pygame.draw.circle(surf, ACCENT,    (self.kx, ty), 7)
        pygame.draw.circle(surf, TEXT_PRI,  (self.kx, ty), 4)
        lbl = self.font.render(f"{self.label}: {int(self.value)}", True, TEXT_SEC)
        surf.blit(lbl, (self.rect.x, self.rect.y - 13))

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if math.hypot(ev.pos[0] - self.kx, ev.pos[1] - self.rect.centery) < 12:
                self.drag = True
        if ev.type == pygame.MOUSEBUTTONUP:
            self.drag = False
        if ev.type == pygame.MOUSEMOTION and self.drag:
            t = (ev.pos[0] - self.rect.x) / self.rect.width
            self.value = self.mn + max(0.0, min(1.0, t)) * (self.mx - self.mn)

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
    _BTN_W = 24

    def __init__(self, rect, value, mn, mx, font):
        self.rect  = pygame.Rect(rect)
        self.value = value
        self.mn    = mn
        self.mx    = mx
        self.font  = font
        bw = self._BTN_W
        self.bd = pygame.Rect(rect[0],               rect[1], bw, rect[3])
        self.bi = pygame.Rect(rect[0] + rect[2] - bw, rect[1], bw, rect[3])

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
        v = self.font.render(str(self.value), True, ACCENT)
        surf.blit(v, v.get_rect(center=self.rect.center))

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.bd.collidepoint(ev.pos):
                self.value = max(self.mn, self.value - 1)
            elif self.bi.collidepoint(ev.pos):
                self.value = min(self.mx, self.value + 1)


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

import pygame

# ── Screen dimensions ──────────────────────────────────────────────────────────
W         = 1200
H         = 850
PANEL_W   = 260
CANVAS_X  = PANEL_W
CANVAS_W  = W - PANEL_W
GRAPH_H   = 160
GRAPH_Y   = H - GRAPH_H
NODE_R    = 8
DEPOT_R   = 12

# ── Physics ────────────────────────────────────────────────────────────────────
PX_TO_KM  = 0.01

# ── Colours ────────────────────────────────────────────────────────────────────
BG          = (  0,   0,   0)
PANEL_BG    = (  5,   5,  30)
BORDER      = ( 33,  33, 200)
TEXT_PRI    = (255, 255,   0)
TEXT_SEC    = (200, 160, 255)
DEPOT_COL   = (255, 255,   0)
ACCENT      = ( 33, 200, 200)
BTN_BG      = (  5,   5,  55)
BTN_HOV     = ( 33,  33, 120)
BTN_SOLVE   = (  0, 160,   0)
BTN_SOLVE_H = (  0, 210,   0)
BTN_CLR     = (180,   0,   0)
BTN_CLR_H   = (230,  40,  40)
BTN_RAND    = (150,   0, 150)
BTN_RAND_H  = (200,  40, 200)
ROUTE_ALPHA = 160
GRAPH_BG    = (  0,   0,  15)
GRAPH_BEST  = (255, 230,   0)
GRAPH_AVG   = (200, 140, 255)
GRAPH_GRID  = ( 18,  18,  70)

VEHICLE_COLORS = [
    (255, 180, 255),
    ( 33, 220, 220),
    (255, 180,  80),
    (255,  80,  80),
    (255, 255,   0),
    (  0, 255, 120),
    (180,  80, 255),
    (255, 255, 255),
]

# ── Sound file names ───────────────────────────────────────────────────────────
SOUND_NAMES = ["waka", "click", "depot", "solve", "victory", "clear", "randomize"]

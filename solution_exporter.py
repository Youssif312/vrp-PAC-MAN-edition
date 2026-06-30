"""
solution_exporter.py
--------------------
Generates a PDF report of the solved VRP routes — one vehicle per page.

Page 1 layout per vehicle:
    Vehicle  Vn
    --------------------------------
    Stop | Customer | Address / Location | Demand
    1    | C5       | 44 Mohamed Mazhar St...  | 10
    2    | C12      | ...                      | 7
    ...
    Route distance: X.XX km   |   Total demand: N

A summary cover page is included first with totals across all vehicles.

Public API
----------
    export_solution_pdf(routes, depot, addresses, out_path) -> (True, path) | (False, error)

The `addresses` dict is keyed as f"C{node.idx}" (matches how app.py builds it
from a dataset's own Address column or the legacy addresses.xlsx fallback).
If an address is not found for a customer the coordinate is shown instead.

Output location
----------------
By default, PDFs are written into an "exports" folder placed next to this
project's .py files (created automatically if missing). Pass an explicit
out_path to override.
"""

import os
import datetime
import hashlib

# ── macOS / LibreSSL compatibility patch ────────────────────────────────────
# Some Python builds (notably python.org installers on macOS linked against
# LibreSSL instead of OpenSSL) reject the `usedforsecurity` keyword that
# reportlab passes to hashlib.md5() internally for non-security fingerprint
# hashing. This wraps hashlib.md5 so it silently drops that kwarg if the
# underlying implementation doesn't accept it — harmless, since reportlab
# never uses MD5 for actual security purposes.
_orig_md5 = hashlib.md5
def _safe_md5(*args, **kwargs):
    try:
        return _orig_md5(*args, **kwargs)
    except TypeError:
        kwargs.pop("usedforsecurity", None)
        return _orig_md5(*args, **kwargs)
hashlib.md5 = _safe_md5

from reportlab.lib.pagesizes   import A4
from reportlab.lib.styles      import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units       import cm
from reportlab.lib             import colors
from reportlab.lib.enums       import TA_LEFT
from reportlab.platypus        import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)

# ── default output folder ──────────────────────────────────────────────────────
# PDFs are saved into an "exports" folder next to the project's .py files.
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")


# ── colour palette (matches app theme) ────────────────────────────────────────
_GOLD    = colors.HexColor("#FFE600")
_PURPLE  = colors.HexColor("#C8A0FF")
_TEAL    = colors.HexColor("#21C8C8")
_DARK    = colors.HexColor("#000820")
_MID     = colors.HexColor("#050532")
_WHITE   = colors.white
_GREY    = colors.HexColor("#AAAAAA")

# one highlight colour per vehicle (wraps after 8)
_V_COLORS = [
    colors.HexColor("#FFB4FF"),
    colors.HexColor("#21DCDC"),
    colors.HexColor("#FFB450"),
    colors.HexColor("#FF5050"),
    colors.HexColor("#FFFF00"),
    colors.HexColor("#00FF78"),
    colors.HexColor("#B450FF"),
    colors.HexColor("#FFFFFF"),
]


# ── helpers ────────────────────────────────────────────────────────────────────

def _route_km(depot, route) -> float:
    import math
    nodes = route.nodes
    if not nodes:
        return 0.0
    def d(ax, ay, bx, by): return math.hypot(bx - ax, by - ay)
    PX_TO_KM = 0.01
    dist  = d(depot.x, depot.y, nodes[0].x, nodes[0].y)
    for i in range(len(nodes) - 1):
        dist += d(nodes[i].x, nodes[i].y, nodes[i+1].x, nodes[i+1].y)
    dist += d(nodes[-1].x, nodes[-1].y, depot.x, depot.y)
    return dist * PX_TO_KM


def _address_for(node, addresses: dict) -> str:
    """Return address string for a node, fall back to coordinates."""
    addr = addresses.get(f"C{node.idx}", addresses.get(str(node.idx), ""))
    if addr:
        return addr
    return f"({node.x:.0f}, {node.y:.0f})"


# ── PDF builder ────────────────────────────────────────────────────────────────

def export_solution_pdf(routes, depot, addresses: dict,
                        out_path: str = None) -> tuple:
    """
    Build the PDF, one vehicle per page after a short summary cover page.

    Parameters
    ----------
    routes    : list of Route objects (from nodes.py)
    depot     : Node object
    addresses : dict  { "C<idx>": address_str }
    out_path  : full file path for the PDF (auto-generated into exports/ if None)

    Returns
    -------
    (True, path)   on success
    (False, error) on failure
    """
    try:
        if out_path is None:
            os.makedirs(DEFAULT_OUT_DIR, exist_ok=True)
            stamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(DEFAULT_OUT_DIR, f"vrp_solution_{stamp}.pdf")
        else:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        doc = SimpleDocTemplate(
            out_path,
            pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm,  bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()

        # Custom styles. Title uses no backColor/borderPadding box (that
        # combination is what previously caused the overlap glitch on the
        # first page) — instead a plain colored HRFlowable rule sits below
        # the title text for the same visual effect, without any layout risk.
        s_title = ParagraphStyle(
            "VRPTitle",
            parent=styles["Title"],
            fontSize=22, leading=26,
            textColor=_GOLD,
            alignment=TA_LEFT,
            spaceAfter=4,
        )
        s_sub = ParagraphStyle(
            "VRPSub",
            parent=styles["Normal"],
            fontSize=9, leading=13,
            textColor=_GREY,
            spaceAfter=4,
        )
        s_vh = ParagraphStyle(
            "VehicleHeader",
            parent=styles["Heading2"],
            fontSize=16, leading=20,
            textColor=_WHITE,
            spaceBefore=0, spaceAfter=6,
        )
        s_summary = ParagraphStyle(
            "RouteSummary",
            parent=styles["Normal"],
            fontSize=10, leading=14,
            textColor=_TEAL,
            spaceBefore=10,
        )
        s_footer = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8, leading=11,
            textColor=_GREY,
            spaceBefore=18,
        )
        s_cover_row = ParagraphStyle(
            "CoverRow",
            parent=styles["Normal"],
            fontSize=10, leading=15,
            textColor=_WHITE,
        )

        story = []

        # ── cover / summary page ─────────────────────────────────────────────
        story.append(Paragraph("PAC-VRP — Route Solution Report", s_title))
        story.append(HRFlowable(width="100%", thickness=1.2, color=_GOLD, spaceAfter=8))

        stamp_str   = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M")
        total_km    = sum(_route_km(depot, r) for r in routes)
        total_stops = sum(len(r.nodes) for r in routes)
        story.append(Paragraph(
            f"Generated: {stamp_str}  |  "
            f"Vehicles: {len(routes)}  |  "
            f"Total stops: {total_stops}  |  "
            f"Total distance: {total_km:.2f} km",
            s_sub,
        ))
        story.append(Spacer(1, 0.4 * cm))

        # quick per-vehicle overview table on the cover page
        cover_data = [["Vehicle", "Stops", "Distance (km)", "Demand"]]
        for r in routes:
            km = _route_km(depot, r)
            demand = sum(n.demand for n in r.nodes)
            cover_data.append([
                f"V{r.vehicle_id + 1}", str(len(r.nodes)),
                f"{km:.2f}", str(demand),
            ])
        cover_tbl = Table(
            cover_data,
            colWidths=[3 * cm, 3 * cm, 4 * cm, 3 * cm],
        )
        cover_tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), _MID),
            ("TEXTCOLOR",   (0, 0), (-1, 0), _GOLD),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("TEXTCOLOR",   (0, 1), (-1, -1), _WHITE),
            ("BACKGROUND",  (0, 1), (-1, -1), _DARK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_DARK, colors.HexColor("#020310")]),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#212180")),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(cover_tbl)
        story.append(Paragraph(
            f"Depot coordinates: ({depot.x:.0f}, {depot.y:.0f})",
            s_footer,
        ))

        # ── one page per vehicle ──────────────────────────────────────────────
        for r in routes:
            story.append(PageBreak())

            v_col  = _V_COLORS[r.vehicle_id % len(_V_COLORS)]
            km     = _route_km(depot, r)
            demand = sum(n.demand for n in r.nodes)

            vh_style = ParagraphStyle(
                f"VH{r.vehicle_id}", parent=s_vh, textColor=v_col,
            )
            story.append(Paragraph(f"Vehicle  V{r.vehicle_id + 1}", vh_style))
            story.append(HRFlowable(width="100%", thickness=1, color=v_col, spaceAfter=10))

            if not r.nodes:
                story.append(Paragraph(
                    "No stops assigned to this vehicle.", s_summary
                ))
                continue

            table_data = [["Stop", "Customer", "Address / Location", "Demand"]]
            for si, node in enumerate(r.nodes):
                cid  = f"C{node.idx}"
                addr = _address_for(node, addresses)
                table_data.append([str(si + 1), cid, addr, str(node.demand)])

            col_widths = [1.4 * cm, 2.6 * cm, 10.5 * cm, 2 * cm]
            tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1,  0), _MID),
                ("TEXTCOLOR",   (0, 0), (-1,  0), v_col),
                ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1,  0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",    (0, 1), (-1, -1), 9),
                ("TEXTCOLOR",   (0, 1), (-1, -1), _WHITE),
                ("BACKGROUND",  (0, 1), (-1, -1), _DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_DARK, colors.HexColor("#020310")]),
                ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#212180")),
                ("ALIGN",       (0, 0), (1,  -1), "CENTER"),
                ("ALIGN",       (3, 0), (3,  -1), "CENTER"),
                ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",  (0, 1), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ]))
            story.append(tbl)

            story.append(Paragraph(
                f"Route distance: {km:.2f} km  |  Total demand served: {demand}",
                s_summary,
            ))

        doc.build(story)
        return True, out_path

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

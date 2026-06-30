"""
solution_exporter.py
--------------------
Generates a PDF report of the solved VRP routes.

Each vehicle section lists:
    V1 → Stop 1: [Customer ID]  →  [Address if available]  (demand: N)
         Stop 2: …
         …
         Total distance: X.XX km   |   Total demand: N

Public API
----------
    export_solution_pdf(routes, depot, addresses, out_path) -> (True, path) | (False, error)

The `addresses` dict comes from dataset_loader.load_addresses().
If an address is not found for a customer ID the coordinate is shown instead.
"""

import os
import datetime

from reportlab.lib.pagesizes   import A4
from reportlab.lib.styles      import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units       import cm
from reportlab.lib             import colors
from reportlab.platypus        import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

# ── default output folder ──────────────────────────────────────────────────────
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
    addr = addresses.get(str(node.idx), addresses.get(f"C{node.idx}", ""))
    if addr:
        return addr
    return f"({node.x:.0f}, {node.y:.0f})"


# ── PDF builder ────────────────────────────────────────────────────────────────

def export_solution_pdf(routes, depot, addresses: dict,
                        out_path: str = None) -> tuple:
    """
    Build the PDF.

    Parameters
    ----------
    routes    : list of Route objects (from nodes.py)
    depot     : Node object
    addresses : dict  { customer_id_str: address_str }
    out_path  : full file path for the PDF (auto-generated if None)

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

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        doc = SimpleDocTemplate(
            out_path,
            pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm,  bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()

        # custom styles
        s_title = ParagraphStyle(
            "VRPTitle",
            parent=styles["Title"],
            fontSize=22, textColor=_GOLD,
            backColor=_DARK, borderPadding=10,
            spaceAfter=6,
        )
        s_sub = ParagraphStyle(
            "VRPSub",
            parent=styles["Normal"],
            fontSize=9, textColor=_GREY,
            spaceAfter=14,
        )
        s_vh = ParagraphStyle(
            "VehicleHeader",
            parent=styles["Heading2"],
            fontSize=13, textColor=_WHITE,
            backColor=_MID, borderPadding=(6, 8, 6, 8),
            spaceBefore=14, spaceAfter=4,
        )
        s_summary = ParagraphStyle(
            "RouteSummary",
            parent=styles["Normal"],
            fontSize=9, textColor=_TEAL,
            spaceAfter=10,
        )
        s_footer = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8, textColor=_GREY,
            spaceBefore=18,
        )

        story = []

        # ── header ────────────────────────────────────────────────────────────
        story.append(Paragraph("PAC-VRP  —  Route Solution Report", s_title))
        stamp_str = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M")
        total_km  = sum(_route_km(depot, r) for r in routes)
        total_stops = sum(len(r.nodes) for r in routes)
        story.append(Paragraph(
            f"Generated: {stamp_str}  |  "
            f"Vehicles: {len(routes)}  |  "
            f"Total stops: {total_stops}  |  "
            f"Total distance: {total_km:.2f} km",
            s_sub,
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=_GOLD, spaceAfter=10))

        # ── per-vehicle sections ───────────────────────────────────────────────
        for r in routes:
            v_col  = _V_COLORS[r.vehicle_id % len(_V_COLORS)]
            km     = _route_km(depot, r)
            demand = sum(n.demand for n in r.nodes)

            # vehicle heading
            story.append(Paragraph(
                f"Vehicle  V{r.vehicle_id + 1}",
                ParagraphStyle(
                    f"VH{r.vehicle_id}",
                    parent=s_vh,
                    textColor=v_col,
                ),
            ))

            if not r.nodes:
                story.append(Paragraph(
                    "No stops assigned to this vehicle.", s_summary
                ))
                continue

            # build stop table
            table_data = [
                ["Stop", "Customer", "Address / Location", "Demand"],
            ]
            for si, node in enumerate(r.nodes):
                cid  = f"C{node.idx}"
                addr = _address_for(node, addresses)
                table_data.append([
                    str(si + 1),
                    cid,
                    addr,
                    str(node.demand),
                ])

            col_widths = [1.2 * cm, 2.5 * cm, 10 * cm, 2 * cm]
            tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(TableStyle([
                # header row
                ("BACKGROUND",  (0, 0), (-1,  0), _MID),
                ("TEXTCOLOR",   (0, 0), (-1,  0), v_col),
                ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1,  0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                # data rows
                ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",    (0, 1), (-1, -1), 9),
                ("TEXTCOLOR",   (0, 1), (-1, -1), _WHITE),
                ("BACKGROUND",  (0, 1), (-1, -1), _DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_DARK, colors.HexColor("#020310")]),
                # grid
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
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#212180"), spaceAfter=4,
            ))

        # ── footer ────────────────────────────────────────────────────────────
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(
            f"Depot coordinates: ({depot.x:.0f}, {depot.y:.0f})  |  "
            f"Total fleet distance: {total_km:.2f} km",
            s_footer,
        ))

        doc.build(story)
        return True, out_path

    except Exception as e:
        return False, str(e)

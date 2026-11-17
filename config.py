# ─────────────────────────────────────────────
# config.py — Theme & Constants
# ─────────────────────────────────────────────

# Color palette (Pistachio + Faint Warm Brown theme)
COLORS = {
    "pista":        "#B7C99A",
    "pista_light":  "#E3EBD7",
    "pista_deep":   "#82966A",
    "brown_faint":  "#B8A18A",
    "brown_box":    "#7A624E",
    "brown_header": "#6B5644",
    "brown_mid":    "#8A6F58",
    "brown_border": "#D0C4B4",
    "pista_border": "#C8D9B0",
    "beige_light":  "#F3EDE5",
    "cream":        "#FAF9F5",
    "text_dark":    "#51483F",
    "white":        "#FFFFFF",
    "red_soft":     "#E8A898",
    "amber_soft":   "#E8C898",
    "blue_soft":    "#98B8D8",
    "lavender":     "#C8B8D8",
}

# Plotly chart colors
CHART_PALETTE = [
    "#82966A",   # deep pista
    "#B8A18A",   # faint warm brown
    "#B7C99A",   # pista
    "#8A6F58",   # brown mid
    "#E8C898",   # amber soft
    "#E8A898",   # red soft
    "#98B8D8",   # blue soft
    "#C8B8D8",   # lavender
]

# App settings
APP_NAME     = "PaySync"
APP_SUBTITLE = "Payment Reconciliation"

# Nav items: (key, label, icon)
NAV_ITEMS = [
    ("overview",        "Overview",        "📊"),
    ("reconciliation",  "Reconciliation",  "⚖️"),
    ("exceptions",      "Exceptions",      "⚠️"),
    ("transactions",    "Transactions",    "📋"),
    ("reports",         "Reports",         "📥"),
]

# Available periods for quick selection
SAMPLE_PERIODS = ["2026-10", "2026-09", "2026-08", "2026-11"]

"""Centralized CustomTkinter theme and appearance configuration for Time Clock.

Defines design tokens (color palettes, typography scales, corner radii, spacing),
appearance mode controllers, and ttk widget styling integrations.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple, Union

import customtkinter as ctk
from tkinter import ttk

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. Color Palettes & Design Tokens (Tuple format: (Light Mode, Dark Mode))
# ==============================================================================

# Background & Surface Palettes
BG_APP: Tuple[str, str] = ("#F3F4F6", "#111216")
BG_CARD: Tuple[str, str] = ("#FFFFFF", "#1E1F24")
BG_CARD_HOVER: Tuple[str, str] = ("#F9FAFB", "#282A30")
BORDER_CARD: Tuple[str, str] = ("#E5E7EB", "#2D3039")
BG_HEADER: Tuple[str, str] = ("#E5E7EB", "#18191D")
BG_SIDEBAR: Tuple[str, str] = ("#ECEFF1", "#16171B")

# Input & Control Backgrounds
BG_INPUT: Tuple[str, str] = ("#FFFFFF", "#2B2D33")
BORDER_INPUT: Tuple[str, str] = ("#D1D5DB", "#3F424E")
BG_SECONDARY_BTN: Tuple[str, str] = ("#E5E7EB", "#2B2D33")
BG_SECONDARY_BTN_HOVER: Tuple[str, str] = ("#D1D5DB", "#3F424E")

# Primary & Brand Accent Colors
PRIMARY: Tuple[str, str] = ("#2563EB", "#3B82F6")
PRIMARY_HOVER: Tuple[str, str] = ("#1D4ED8", "#2563EB")
SECONDARY: Tuple[str, str] = ("#64748B", "#475569")
SECONDARY_HOVER: Tuple[str, str] = ("#475569", "#334155")

# Semantic Status Colors (Action, State Feedback)
SUCCESS: Tuple[str, str] = ("#16A34A", "#22C55E")          # Clock In / Paid / Positive
SUCCESS_HOVER: Tuple[str, str] = ("#15803D", "#16A34A")
SUCCESS_BG: Tuple[str, str] = ("#DCFCE7", "#143D24")

DANGER: Tuple[str, str] = ("#DC2626", "#EF4444")           # Clock Out / Stop / Delete
DANGER_HOVER: Tuple[str, str] = ("#B91C1C", "#DC2626")
DANGER_BG: Tuple[str, str] = ("#FEE2E2", "#451A1A")

WARNING: Tuple[str, str] = ("#D97706", "#F59E0B")          # Alert / Behind Pace / Unreported
WARNING_HOVER: Tuple[str, str] = ("#B45309", "#D97706")
WARNING_BG: Tuple[str, str] = ("#FEF3C7", "#422006")

INFO: Tuple[str, str] = ("#0284C7", "#38BDF8")             # Informational / Blue Accent
INFO_HOVER: Tuple[str, str] = ("#0369A1", "#0284C7")
INFO_BG: Tuple[str, str] = ("#E0F2FE", "#0C4A6E")

MUTED: Tuple[str, str] = ("#6B7280", "#9CA3AF")

# Typography & Text Colors
TEXT_PRIMARY: Tuple[str, str] = ("#111827", "#F9FAFB")
TEXT_SECONDARY: Tuple[str, str] = ("#4B5563", "#9CA3AF")
TEXT_MUTED: Tuple[str, str] = ("#6B7280", "#9CA3AF")
TEXT_WHITE: str = "#FFFFFF"
TEXT_DARK: str = "#111827"

# Status Badges & Tag Colors (high contrast across light & dark modes)
TAG_PAID: Tuple[str, str] = ("#16A34A", "#22C55E")
TAG_UNPAID: Tuple[str, str] = ("#4B5563", "#9CA3AF")
TAG_UNREPORTED: Tuple[str, str] = ("#B45309", "#F59E0B")
TAG_ARCHIVED: Tuple[str, str] = ("#6B7280", "#9CA3AF")
TAG_REPORTED: Tuple[str, str] = ("#6B7280", "#9CA3AF")

# Progress Bars & Needle Indicators
PROGRESS_BG: Tuple[str, str] = ("#E5E7EB", "#2D3039")
PROGRESS_FILL: Tuple[str, str] = ("#2563EB", "#3B82F6")
PROGRESS_SUCCESS: Tuple[str, str] = ("#16A34A", "#22C55E")
PROGRESS_WARNING: Tuple[str, str] = ("#D97706", "#F59E0B")
PACE_NEEDLE: Tuple[str, str] = ("#D97706", "#F59E0B")


# ==============================================================================
# 2. Dimensions, Corner Radii & Spacing Constants
# ==============================================================================

# Corner Radii
RADIUS_CARD: int = 12
RADIUS_BUTTON: int = 8
RADIUS_CHIP: int = 6
RADIUS_INPUT: int = 6
RADIUS_DIALOG: int = 14
RADIUS_BADGE: int = 4
RADIUS_PROGRESS: int = 6

# Spacing & Padding
PAD_XS: int = 4
PAD_SM: int = 8
PAD_MD: int = 12
PAD_LG: int = 16
PAD_XL: int = 24


# ==============================================================================
# 3. Typography Scales & Font Tokens
# ==============================================================================

SANS_FONT_CANDIDATES = [
    "SF Pro Display",
    "SF Pro Text",
    "SF Pro",
    "Helvetica Neue",
    "Segoe UI",
    "Ubuntu",
    "DejaVu Sans",
    "Arial",
]

MONO_FONT_CANDIDATES = [
    "SF Mono",
    "Menlo",
    "Consolas",
    "DejaVu Sans Mono",
    "Courier New",
    "Courier",
]


def resolve_font_family(category: str = "sans") -> str:
    """Resolve the best available font family for the current platform/Tk environment.

    Args:
        category: 'sans' for proportional UI text or 'mono' for fixed-width stopwatch/code.

    Returns:
        Font family name string that is verified available in Tkinter.
    """
    candidates = MONO_FONT_CANDIDATES if category == "mono" else SANS_FONT_CANDIDATES
    fallback_named = "TkFixedFont" if category == "mono" else "TkDefaultFont"
    fallback_family = "Courier" if category == "mono" else "Helvetica"
    try:
        import tkinter.font as tkfont

        available = set(tkfont.families())
        for font_name in candidates:
            if font_name in available:
                if category == "mono":
                    # Verify that font actually measures as fixed-width
                    f = tkfont.Font(family=font_name, size=12)
                    if f.metrics("fixed"):
                        return font_name
                else:
                    return font_name
        # Fall back to Tk named fonts if none matched directly
        named = tkfont.nametofont(fallback_named)
        family = named.actual().get("family")
        if family:
            return family
    except Exception:
        # Courier is Tk's portable fixed-width family; named-font identifiers
        # cannot safely be used as CTkFont family values before a root exists.
        return fallback_family
    return fallback_family


FONT_FAMILY_SANS: str = resolve_font_family("sans")
FONT_FAMILY_MONO: str = resolve_font_family("mono")

# Preset font specifications: (family, size, weight)
FONT_HERO = (FONT_FAMILY_SANS, 40, "bold")
FONT_HERO_MONO = (FONT_FAMILY_MONO, 42, "bold")
FONT_HERO_SUB = (FONT_FAMILY_SANS, 22, "bold")
FONT_TITLE = (FONT_FAMILY_SANS, 20, "bold")
FONT_SUBTITLE = (FONT_FAMILY_SANS, 17, "bold")
FONT_SECTION = (FONT_FAMILY_SANS, 16, "bold")
FONT_BODY = (FONT_FAMILY_SANS, 14, "normal")
FONT_BODY_BOLD = (FONT_FAMILY_SANS, 14, "bold")
FONT_CAPTION = (FONT_FAMILY_SANS, 12, "normal")
FONT_CAPTION_BOLD = (FONT_FAMILY_SANS, 12, "bold")
FONT_MONO = (FONT_FAMILY_MONO, 13, "normal")
FONT_MONO_BOLD = (FONT_FAMILY_MONO, 13, "bold")


def update_font_tokens() -> None:
    """Refresh font family variables and presets once Tkinter is initialized."""
    global FONT_FAMILY_SANS, FONT_FAMILY_MONO
    global FONT_HERO, FONT_HERO_MONO, FONT_HERO_SUB, FONT_TITLE, FONT_SUBTITLE
    global FONT_SECTION, FONT_BODY, FONT_BODY_BOLD, FONT_CAPTION, FONT_CAPTION_BOLD
    global FONT_MONO, FONT_MONO_BOLD

    FONT_FAMILY_SANS = resolve_font_family("sans")
    FONT_FAMILY_MONO = resolve_font_family("mono")

    FONT_HERO = (FONT_FAMILY_SANS, 40, "bold")
    FONT_HERO_MONO = (FONT_FAMILY_MONO, 42, "bold")
    FONT_HERO_SUB = (FONT_FAMILY_SANS, 22, "bold")
    FONT_TITLE = (FONT_FAMILY_SANS, 20, "bold")
    FONT_SUBTITLE = (FONT_FAMILY_SANS, 17, "bold")
    FONT_SECTION = (FONT_FAMILY_SANS, 16, "bold")
    FONT_BODY = (FONT_FAMILY_SANS, 14, "normal")
    FONT_BODY_BOLD = (FONT_FAMILY_SANS, 14, "bold")
    FONT_CAPTION = (FONT_FAMILY_SANS, 12, "normal")
    FONT_CAPTION_BOLD = (FONT_FAMILY_SANS, 12, "bold")
    FONT_MONO = (FONT_FAMILY_MONO, 13, "normal")
    FONT_MONO_BOLD = (FONT_FAMILY_MONO, 13, "bold")


def get_font(
    size: int = 14,
    weight: str = "normal",
    family: Optional[str] = None,
    mono: bool = False,
    slant: str = "roman",
    underline: bool = False,
    overstrike: bool = False,
) -> ctk.CTkFont:
    """Return a configured CTkFont instance with runtime family resolution.

    Args:
        size: Font point size.
        weight: 'normal' or 'bold'.
        family: Optional font family name (defaults to resolved sans family).
        mono: If True, uses the resolved fixed-width mono family.
        slant: 'roman' or 'italic'.
        underline: Boolean flag for underline style.
        overstrike: Boolean flag for strikethrough style.

    Returns:
        ctk.CTkFont configured with the specified parameters.
    """
    update_font_tokens()
    if family:
        font_family = family
    elif mono:
        font_family = FONT_FAMILY_MONO
    else:
        font_family = FONT_FAMILY_SANS

    return ctk.CTkFont(
        family=font_family,
        size=size,
        weight=weight,
        slant=slant,
        underline=underline,
        overstrike=overstrike,
    )


# ==============================================================================
# 4. Color Resolution & Mode Helpers
# ==============================================================================

ColorType = Union[str, Tuple[str, str]]


def is_dark_mode() -> bool:
    """Check whether the active appearance mode is Dark."""
    mode = ctk.get_appearance_mode().lower()
    return mode == "dark"


def resolve_color(
    color: ColorType,
    appearance_mode: Optional[str] = None,
) -> str:
    """Resolve a single hex color string from a color tuple or single string.

    Args:
        color: A hex color string or (light_color, dark_color) tuple.
        appearance_mode: Optional explicit mode override ('Light' or 'Dark').
            If not provided, uses the active CustomTkinter appearance mode.

    Returns:
        Hex color string for the active mode.
    """
    if isinstance(color, str):
        return color

    if appearance_mode is not None:
        dark = appearance_mode.lower() == "dark"
    else:
        dark = is_dark_mode()

    return color[1] if dark else color[0]


# ==============================================================================
# 5. TTK Widget Styling Integration
# ==============================================================================

def style_treeview(style: ttk.Style, dark_mode: Optional[bool] = None) -> None:
    """Configure ttk.Treeview and related Tk widgets to blend with CTk styling.

    Args:
        style: The ttk.Style instance associated with the active root window.
        dark_mode: Explicit dark mode boolean override, or None to auto-detect.
    """
    update_font_tokens()
    dark = dark_mode if dark_mode is not None else is_dark_mode()
    mode_str = "dark" if dark else "light"

    # Select 'clam' theme if available for custom background/header colors across platforms
    if "clam" in style.theme_names() and style.theme_use() != "clam":
        try:
            style.theme_use("clam")
        except Exception as e:
            logger.warning("Could not set ttk theme to clam: %s", e)

    bg_card = resolve_color(BG_CARD, mode_str)
    bg_row_hover = resolve_color(BG_CARD_HOVER, mode_str)
    border_card = resolve_color(BORDER_CARD, mode_str)
    header_bg = resolve_color(BG_HEADER, mode_str)
    text_primary = resolve_color(TEXT_PRIMARY, mode_str)
    text_secondary = resolve_color(TEXT_SECONDARY, mode_str)
    primary_sel = resolve_color(PRIMARY, mode_str)

    try:
        style.configure(
            "Treeview",
            background=bg_card,
            foreground=text_primary,
            fieldbackground=bg_card,
            rowheight=32,
            borderwidth=0,
            relief="flat",
            font=(FONT_FAMILY_SANS, 13, "normal"),
        )
        style.map(
            "Treeview",
            background=[("selected", primary_sel), ("hover", bg_row_hover)],
            foreground=[("selected", TEXT_WHITE), ("hover", text_primary)],
        )

        style.configure(
            "Treeview.Heading",
            background=header_bg,
            foreground=text_secondary,
            relief="flat",
            borderwidth=1,
            font=(FONT_FAMILY_SANS, 12, "bold"),
            padding=(8, 6),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", border_card)],
            foreground=[("active", text_primary)],
        )
    except Exception as e:
        logger.warning("Error configuring Treeview styles: %s", e)


# ==============================================================================
# 6. Global Theme Initialization
# ==============================================================================

def set_appearance_mode(mode: str) -> None:
    """Set global appearance mode ('System', 'Light', or 'Dark')."""
    ctk.set_appearance_mode(mode)


def get_appearance_mode() -> str:
    """Get the current appearance mode."""
    return ctk.get_appearance_mode()


def set_color_theme(theme_name: str) -> None:
    """Set CustomTkinter color theme."""
    ctk.set_default_color_theme(theme_name)


def init_theme(
    appearance_mode: str = "System",
    color_theme: str = "blue",
) -> None:
    """Initialize CustomTkinter global theme and appearance settings.

    Args:
        appearance_mode: 'System', 'Dark', or 'Light'.
        color_theme: Color theme name or JSON theme file path (default 'blue').
    """
    try:
        set_appearance_mode(appearance_mode)
        set_color_theme(color_theme)
        update_font_tokens()
    except Exception as e:
        logger.warning("Error initializing theme settings: %s", e)

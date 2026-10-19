"""Unit tests for time_clock.gui.theme module."""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import unittest

import customtkinter as ctk

from time_clock.gui import theme


class TestTheme(unittest.TestCase):
    """Test suite for design tokens, typography, and theme configuration."""

    def setUp(self):
        self._orig_mode = ctk.get_appearance_mode()
        try:
            self.root = ctk.CTk()
            self.root.withdraw()
        except tk.TclError:
            self.skipTest("Tkinter display not available in this test environment.")

    def tearDown(self):
        if hasattr(self, "_orig_mode"):
            theme.set_appearance_mode(self._orig_mode)
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_color_tokens_defined(self):
        """Verify color tokens are properly defined as (light, dark) tuples or hex strings."""
        self.assertIsInstance(theme.BG_APP, tuple)
        self.assertEqual(len(theme.BG_APP), 2)
        self.assertIsInstance(theme.BG_CARD, tuple)
        self.assertEqual(len(theme.BG_CARD), 2)
        self.assertIsInstance(theme.PRIMARY, tuple)
        self.assertEqual(len(theme.PRIMARY), 2)
        self.assertIsInstance(theme.SUCCESS, tuple)
        self.assertEqual(len(theme.SUCCESS), 2)
        self.assertIsInstance(theme.DANGER, tuple)
        self.assertEqual(len(theme.DANGER), 2)
        self.assertIsInstance(theme.WARNING, tuple)
        self.assertEqual(len(theme.WARNING), 2)
        self.assertIsInstance(theme.TEXT_PRIMARY, tuple)
        self.assertEqual(len(theme.TEXT_PRIMARY), 2)

    def test_radii_and_spacing_constants(self):
        """Verify radius and spacing tokens are positive integers."""
        self.assertGreater(theme.RADIUS_CARD, 0)
        self.assertGreater(theme.RADIUS_BUTTON, 0)
        self.assertGreater(theme.RADIUS_CHIP, 0)
        self.assertGreater(theme.RADIUS_INPUT, 0)
        self.assertGreater(theme.RADIUS_DIALOG, 0)
        self.assertGreater(theme.PAD_XS, 0)
        self.assertGreater(theme.PAD_SM, 0)
        self.assertGreater(theme.PAD_MD, 0)
        self.assertGreater(theme.PAD_LG, 0)
        self.assertGreater(theme.PAD_XL, 0)

    def test_font_factory_and_fixed_metrics(self):
        """Verify get_font generates valid CTkFont objects and mono font is fixed-width."""
        theme.update_font_tokens()
        self.assertTrue(bool(theme.FONT_FAMILY_SANS))
        self.assertTrue(bool(theme.FONT_FAMILY_MONO))

        # Verify mono font produces fixed-width metrics
        mono_font = tkfont.Font(family=theme.FONT_FAMILY_MONO, size=12)
        self.assertEqual(
            mono_font.metrics("fixed"),
            1,
            f"Expected fixed-width metrics for mono font family '{theme.FONT_FAMILY_MONO}'",
        )

        font_default = theme.get_font()
        self.assertIsInstance(font_default, ctk.CTkFont)
        self.assertEqual(font_default.cget("size"), 14)

        font_sans = theme.get_font(size=14, weight="bold", mono=False)
        self.assertIsInstance(font_sans, ctk.CTkFont)
        self.assertEqual(font_sans.cget("size"), 14)
        self.assertEqual(font_sans.cget("weight"), "bold")

        font_mono = theme.get_font(size=12, weight="normal", mono=True)
        self.assertIsInstance(font_mono, ctk.CTkFont)
        self.assertEqual(font_mono.cget("size"), 12)

    def test_typography_scale_tokens(self):
        """Verify centralized typography scale definitions match the upgraded point sizes."""
        theme.update_font_tokens()
        self.assertEqual(theme.FONT_HERO[1:], (40, "bold"))
        self.assertEqual(theme.FONT_HERO_MONO[1:], (42, "bold"))
        self.assertEqual(theme.FONT_HERO_SUB[1:], (22, "bold"))
        self.assertEqual(theme.FONT_TITLE[1:], (20, "bold"))
        self.assertEqual(theme.FONT_SUBTITLE[1:], (17, "bold"))
        self.assertEqual(theme.FONT_SECTION[1:], (16, "bold"))
        self.assertEqual(theme.FONT_BODY[1:], (14, "normal"))
        self.assertEqual(theme.FONT_BODY_BOLD[1:], (14, "bold"))
        self.assertEqual(theme.FONT_CAPTION[1:], (12, "normal"))
        self.assertEqual(theme.FONT_CAPTION_BOLD[1:], (12, "bold"))
        self.assertEqual(theme.FONT_MONO[1:], (13, "normal"))
        self.assertEqual(theme.FONT_MONO_BOLD[1:], (13, "bold"))

    def test_pre_root_theme_initialization_keeps_mono_token_fixed_width(self):
        """Verify the pre-root token remains fixed-width after Tk creates its default root."""
        self.root.destroy()
        self.root = None

        theme.init_theme(appearance_mode="System")
        mono_token = theme.FONT_HERO_MONO

        self.root = ctk.CTk()
        self.root.withdraw()
        mono_font = tkfont.Font(family=mono_token[0], size=mono_token[1])
        self.assertEqual(
            mono_font.metrics("fixed"),
            1,
            f"Expected pre-root mono token family '{mono_token[0]}' to be fixed-width",
        )

    def test_resolve_color(self):
        """Verify color resolution across light and dark modes with explicit and auto mode."""
        sample_tuple = ("#FFFFFF", "#000000")
        # Explicit appearance_mode parameter
        self.assertEqual(theme.resolve_color(sample_tuple, appearance_mode="Light"), "#FFFFFF")
        self.assertEqual(theme.resolve_color(sample_tuple, appearance_mode="Dark"), "#000000")
        self.assertEqual(theme.resolve_color("#123456", appearance_mode="Light"), "#123456")

        # Implicit appearance mode via active CTk mode
        theme.set_appearance_mode("Dark")
        self.assertEqual(theme.resolve_color(sample_tuple), "#000000")
        theme.set_appearance_mode("Light")
        self.assertEqual(theme.resolve_color(sample_tuple), "#FFFFFF")

    def test_theme_mode_lifecycle(self):
        """Verify setting appearance mode and color theme."""
        theme.set_appearance_mode("Dark")
        self.assertEqual(theme.get_appearance_mode(), "Dark")
        self.assertTrue(theme.is_dark_mode())

        theme.set_appearance_mode("Light")
        self.assertEqual(theme.get_appearance_mode(), "Light")
        self.assertFalse(theme.is_dark_mode())

        theme.init_theme(appearance_mode="Dark", color_theme="blue")
        self.assertEqual(theme.get_appearance_mode(), "Dark")

    def test_style_treeview(self):
        """Verify ttk.Treeview theme configuration values for both Light and Dark modes."""
        style = ttk.Style(self.root)

        # Test Light mode styling
        theme.style_treeview(style, dark_mode=False)
        self.assertEqual(
            style.lookup("Treeview", "background"),
            theme.resolve_color(theme.BG_CARD, "Light"),
        )
        self.assertEqual(
            style.lookup("Treeview", "fieldbackground"),
            theme.resolve_color(theme.BG_CARD, "Light"),
        )
        self.assertEqual(
            style.lookup("Treeview.Heading", "background"),
            theme.resolve_color(theme.BG_HEADER, "Light"),
        )
        self.assertEqual(
            style.lookup("Treeview", "foreground"),
            theme.resolve_color(theme.TEXT_PRIMARY, "Light"),
        )
        self.assertEqual(int(style.configure("Treeview", "rowheight")), 32)
        tree_font = str(style.configure("Treeview", "font"))
        self.assertIn(str(theme.FONT_FAMILY_SANS), tree_font)
        self.assertIn("13", tree_font)
        self.assertIn("normal", tree_font)

        heading_font = str(style.configure("Treeview.Heading", "font"))
        self.assertIn(str(theme.FONT_FAMILY_SANS), heading_font)
        self.assertIn("12", heading_font)
        self.assertIn("bold", heading_font)

        # Padding can be tuple (8, 6) or string/list in different Tcl versions
        padding_val = style.configure("Treeview.Heading", "padding")
        if isinstance(padding_val, (tuple, list)):
            self.assertEqual(tuple(int(x) for x in padding_val), (8, 6))
        else:
            self.assertIn("8", str(padding_val))
            self.assertIn("6", str(padding_val))

        # Test Dark mode styling
        theme.style_treeview(style, dark_mode=True)
        self.assertEqual(
            style.lookup("Treeview", "background"),
            theme.resolve_color(theme.BG_CARD, "Dark"),
        )
        self.assertEqual(
            style.lookup("Treeview", "fieldbackground"),
            theme.resolve_color(theme.BG_CARD, "Dark"),
        )
        self.assertEqual(
            style.lookup("Treeview.Heading", "background"),
            theme.resolve_color(theme.BG_HEADER, "Dark"),
        )
        self.assertEqual(
            style.lookup("Treeview", "foreground"),
            theme.resolve_color(theme.TEXT_PRIMARY, "Dark"),
        )
        self.assertEqual(int(style.configure("Treeview", "rowheight")), 32)
        tree_font = str(style.configure("Treeview", "font"))
        self.assertIn(str(theme.FONT_FAMILY_SANS), tree_font)
        self.assertIn("13", tree_font)
        self.assertIn("normal", tree_font)

        heading_font = str(style.configure("Treeview.Heading", "font"))
        self.assertIn(str(theme.FONT_FAMILY_SANS), heading_font)
        self.assertIn("12", heading_font)
        self.assertIn("bold", heading_font)

        # Padding can be tuple (8, 6) or string/list in different Tcl versions
        padding_val = style.configure("Treeview.Heading", "padding")
        if isinstance(padding_val, (tuple, list)):
            self.assertEqual(tuple(int(x) for x in padding_val), (8, 6))
        else:
            self.assertIn("8", str(padding_val))
            self.assertIn("6", str(padding_val))


if __name__ == "__main__":
    unittest.main()

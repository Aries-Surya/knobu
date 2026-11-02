"""Knobu's look: a neutral, theme-following stylesheet and its own icons.

Colour is kept for meaning only: the system accent marks the selected page, green
means on/running, and the warning colour marks setup notices."""

from pathlib import Path

from gi.repository import Gdk, Gtk

# Knobu ships its own symbolic icons so the tiles look the same with every icon theme.
ICONS_DIR = Path(__file__).parent / "icons"


CSS = """
.tile {
  color: @window_fg_color;
  background-color: alpha(@window_fg_color, 0.08);
  border-radius: 9px;
  min-width: 28px;
  min-height: 28px;
}
.tile.small { min-width: 26px; min-height: 26px; border-radius: 7px; }
.tile.medium { min-width: 40px; min-height: 40px; border-radius: 11px; }
.tile.large { min-width: 60px; min-height: 60px; border-radius: 16px; }
row:selected .tile { background-color: @accent_bg_color; color: @accent_fg_color; }

.hero { padding: 6px 2px 18px 2px; }
.hero-subtitle { font-size: 1.05em; }

.module-card {
  padding: 18px;
  border-radius: 16px;
  transition: box-shadow 150ms ease;
}
/* The grid cells are invisible: only the card itself reacts to hover and focus. */
flowbox.module-grid > flowboxchild,
flowbox.module-grid > flowboxchild:hover,
flowbox.module-grid > flowboxchild:active,
flowbox.module-grid > flowboxchild:selected,
flowbox.module-grid > flowboxchild:focus,
flowbox.module-grid > flowboxchild:focus-visible {
  padding: 0;
  background: none;
  box-shadow: none;
  outline: none;
}
flowbox.module-grid > flowboxchild:hover .module-card {
  box-shadow: inset 0 0 0 1px alpha(@window_fg_color, 0.15);
}
flowbox.module-grid > flowboxchild:focus-visible .module-card {
  box-shadow: inset 0 0 0 2px @accent_color;
}
.module-card .summary { font-size: 0.9em; }

.keycap {
  font-family: monospace;
  font-weight: 700;
  font-size: 0.85em;
  padding: 2px 8px;
  border-radius: 6px;
  background-color: alpha(@window_fg_color, 0.08);
  box-shadow: inset 0 -2px alpha(@window_fg_color, 0.14);
}

.pill {
  border-radius: 999px;
  padding: 4px 12px;
  font-weight: 700;
  font-size: 0.9em;
}
.pill.running { background-color: alpha(@success_color, 0.15); color: @success_color; }
.pill.stopped { background-color: alpha(@window_fg_color, 0.08); }

.dot { min-width: 8px; min-height: 8px; border-radius: 999px;
       background-color: alpha(@window_fg_color, 0.2); }
.dot.on { background-color: @success_color; }

.sidebar-heading { font-size: 0.8em; font-weight: 700; letter-spacing: 0.06em;
                   margin: 14px 18px 4px 18px; }
.sidebar-footer { padding: 10px 18px 14px 18px; font-size: 0.9em; }

.notice { padding: 14px; border-radius: 14px;
          background-color: alpha(@warning_color, 0.12); }
.notice .command { font-family: monospace; font-size: 0.9em; }
"""


def apply() -> None:
    display = Gdk.Display.get_default()
    Gtk.IconTheme.get_for_display(display).add_search_path(str(ICONS_DIR))
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(display, provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

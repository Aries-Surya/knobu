"""GTK4 + libadwaita settings app."""

import gi

# Pinned here, before any submodule imports from gi.repository.
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

"""GTK4 + libadwaita settings app and tool windows."""

import gi

# Pinned here, before any submodule imports from gi.repository.
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

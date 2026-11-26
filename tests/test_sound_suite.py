"""Hardcore unit & integration tests for Milestone 2: Per-App Volume Mixer & Sound Suite."""

import unittest
from unittest.mock import MagicMock, patch

from knobu.modules.sound import (
    SoundSuiteModule,
    cycle_output_sink,
    parse_wpctl_status,
    set_stream_volume,
    toggle_mic_mute,
    toggle_stream_mute,
)


SAMPLE_WPCTL_STATUS = """
PipeWire 'pipewire-0' [1.6.2]
Audio
 ├─ Devices:
 │      52. Built-in Audio                      [alsa]
 ├─ Sinks:
 │  *   57. Built-in Audio Analog Stereo        [vol: 0.75]
 │      61. WH-1000XM5 Bluetooth                [vol: 0.50 MUTED]
 ├─ Sources:
 │  *   58. Built-in Audio Analog Stereo        [vol: 0.32]
 └─ Streams:
        84. Chromium
             78. output_FR       > ALC3204 Analog:playback_FR [active]
        92. Spotify
             93. output_FL       > ALC3204 Analog:playback_FL [active]
"""


class TestSoundSuite(unittest.TestCase):
    def test_parse_wpctl_status_sinks_sources_streams(self):
        sinks, sources, streams = parse_wpctl_status(SAMPLE_WPCTL_STATUS)
        self.assertEqual(len(sinks), 2)
        self.assertTrue(sinks[0].is_default)
        self.assertEqual(sinks[0].id, 57)
        self.assertEqual(sinks[0].volume, 75)
        self.assertFalse(sinks[0].muted)
        self.assertEqual(sinks[1].id, 61)
        self.assertTrue(sinks[1].muted)
        self.assertEqual(len(sources), 1)
        self.assertEqual([s.app_name for s in streams], ["Chromium", "Spotify"])

    def test_stream_volume_boost_clamping(self):
        with patch("knobu.modules.sound._run_wpctl", return_value=(0, "")) as mock_run:
            ok, _ = set_stream_volume(84, 150)
            self.assertTrue(ok)
            mock_run.assert_called_with("set-volume", "-l", "1.5", "84", "150%")

            set_stream_volume(84, 250)  # clamp to 150
            mock_run.assert_called_with("set-volume", "-l", "1.5", "84", "150%")

            set_stream_volume(84, -10)  # clamp to 0
            mock_run.assert_called_with("set-volume", "-l", "1.5", "84", "0%")

    def test_stream_and_mic_mute(self):
        with patch("knobu.modules.sound._run_wpctl", return_value=(0, "")) as mock_run:
            ok, _ = toggle_stream_mute(84)
            self.assertTrue(ok)
            mock_run.assert_called_with("set-mute", "84", "toggle")

        with patch("knobu.modules.sound._run_wpctl", return_value=(0, "Volume: 0.32 [MUTED]")), \
             patch("knobu.modules.sound.get_mic_status", return_value=(32, True)):
            ok, msg = toggle_mic_mute()
            self.assertTrue(ok)
            self.assertEqual(msg, "Microphone Muted")

    def test_cycle_output_sink(self):
        with patch("knobu.modules.sound._run_wpctl", return_value=(0, SAMPLE_WPCTL_STATUS)), \
             patch("knobu.modules.sound.get_node_volume", return_value=(100, False)), \
             patch("knobu.modules.sound.set_default_sink", return_value=(True, "ok")) as mock_set:
            ok, msg = cycle_output_sink()
            self.assertTrue(ok)
            mock_set.assert_called_once_with(61)
            self.assertIn("WH-1000XM5", msg)

    def test_ui_sound_page_builds(self):
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        Adw.init()
        from knobu.ui.pages import sound_page
        from knobu.ui.store import SettingsStore
        w = sound_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(w)


if __name__ == "__main__":
    unittest.main()

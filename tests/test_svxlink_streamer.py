#!/usr/bin/env python3

import unittest

from unittest.mock import patch

from streamer import svxlink_streamer as streamer


class CTCSSConfigurationTests(unittest.TestCase):

    def test_changed_frequency_requires_encoder_restart(self):
        with patch.object(
            streamer,
            "tx_ctcss_frequency",
            return_value=94.8,
        ):
            self.assertTrue(
                streamer.ctcss_frequency_changed(88.5)
            )

    def test_unchanged_frequency_does_not_restart_encoder(self):
        with patch.object(
            streamer,
            "tx_ctcss_frequency",
            return_value=88.5,
        ):
            self.assertFalse(
                streamer.ctcss_frequency_changed(88.5)
            )

    def test_adding_ctcss_requires_encoder_restart(self):
        with patch.object(
            streamer,
            "tx_ctcss_frequency",
            return_value=88.5,
        ):
            self.assertTrue(
                streamer.ctcss_frequency_changed(None)
            )

    def test_removing_ctcss_requires_encoder_restart(self):
        with patch.object(
            streamer,
            "tx_ctcss_frequency",
            return_value=None,
        ):
            self.assertTrue(
                streamer.ctcss_frequency_changed(88.5)
            )


if __name__ == "__main__":
    unittest.main()

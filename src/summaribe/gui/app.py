"""wx.App entry point."""

from __future__ import annotations

import wx

from summaribe.core.config import SettingsManager
from summaribe.core.logging_setup import configure_logging


def main() -> None:
    configure_logging(SettingsManager().settings.log_level)
    app = wx.App(False)
    # Screen readers announce the application name alongside the window title, and
    # assistive tech identifies the process by it, so set it explicitly.
    app.SetAppName("SummaRibe")
    app.SetAppDisplayName("SummaRibe")
    from summaribe.gui.main_frame import MainFrame

    frame = MainFrame(None)
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()

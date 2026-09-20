"""wx.App entry point."""

from __future__ import annotations

import wx


def main() -> None:
    app = wx.App(False)
    from summaribe.gui.main_frame import MainFrame

    frame = MainFrame(None)
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()

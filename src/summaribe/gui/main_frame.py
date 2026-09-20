"""Top-level window: one tab per concern (pipeline, providers, prompts, dictionary, settings)."""

from __future__ import annotations

import wx

from summaribe.core.config import SettingsManager
from summaribe.gui.dictionary_editor import DictionaryEditorPanel
from summaribe.gui.pipeline_panel import PipelinePanel
from summaribe.gui.prompt_editor import PromptEditorPanel
from summaribe.gui.provider_editor import ProviderEditorPanel
from summaribe.gui.settings_panel import SettingsPanel

_DARK_BG = wx.Colour(30, 30, 30)
_DARK_FG = wx.Colour(230, 230, 230)
_LIGHT_BG = wx.Colour(255, 255, 255)
_LIGHT_FG = wx.Colour(0, 0, 0)


def apply_theme(window: wx.Window, theme: str) -> None:
    """Recursively override colours for `theme` in {"light", "dark"}; a no-op
    for "system", which just leaves the platform's own colours in place."""
    if theme not in ("light", "dark"):
        return
    bg, fg = (_DARK_BG, _DARK_FG) if theme == "dark" else (_LIGHT_BG, _LIGHT_FG)

    def _recurse(win: wx.Window) -> None:
        win.SetBackgroundColour(bg)
        win.SetForegroundColour(fg)
        for child in win.GetChildren():
            _recurse(child)
        win.Refresh()

    _recurse(window)


class MainFrame(wx.Frame):
    def __init__(self, parent: wx.Window | None) -> None:
        self.settings_manager = SettingsManager()
        gui_settings = self.settings_manager.settings.gui
        super().__init__(
            parent,
            title="SummaRibe",
            size=(gui_settings.window_width, gui_settings.window_height),
        )

        notebook = wx.Notebook(self)
        notebook.AddPage(PipelinePanel(notebook, self.settings_manager), "Pipeline")
        notebook.AddPage(ProviderEditorPanel(notebook), "Providers")
        notebook.AddPage(PromptEditorPanel(notebook), "Prompts")
        notebook.AddPage(DictionaryEditorPanel(notebook), "Dictionary")
        notebook.AddPage(SettingsPanel(notebook, self.settings_manager), "Settings")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.CreateStatusBar()
        self.SetStatusText("Ready")

        apply_theme(self, gui_settings.theme)

        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_close(self, event: wx.CloseEvent) -> None:
        width, height = self.GetSize()
        settings = self.settings_manager.settings
        settings.gui.window_width = width
        settings.gui.window_height = height
        self.settings_manager.save(settings)
        event.Skip()

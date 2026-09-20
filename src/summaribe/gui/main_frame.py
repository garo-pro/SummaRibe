"""Top-level window: one tab per concern (pipeline, providers, prompts, dictionary, settings)."""

from __future__ import annotations

import wx

from summaribe.core.config import SettingsManager
from summaribe.gui.dictionary_editor import DictionaryEditorPanel
from summaribe.gui.pipeline_panel import PipelinePanel
from summaribe.gui.prompt_editor import PromptEditorPanel
from summaribe.gui.provider_editor import ProviderEditorPanel
from summaribe.gui.settings_panel import SettingsPanel


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

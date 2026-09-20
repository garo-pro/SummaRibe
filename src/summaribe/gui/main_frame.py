"""Top-level window: one tab per concern (pipeline, providers, prompts, dictionary, settings)."""

from __future__ import annotations

import wx

from summaribe.core.config import SettingsManager
from summaribe.gui.accessibility import describe, uses_high_contrast
from summaribe.gui.dictionary_editor import DictionaryEditorPanel
from summaribe.gui.pipeline_panel import PipelinePanel
from summaribe.gui.prompt_editor import PromptEditorPanel
from summaribe.gui.provider_editor import ProviderEditorPanel
from summaribe.gui.settings_panel import SettingsPanel

_DARK_BG = wx.Colour(30, 30, 30)
_DARK_FG = wx.Colour(230, 230, 230)
_LIGHT_BG = wx.Colour(255, 255, 255)
_LIGHT_FG = wx.Colour(0, 0, 0)

_TABS = ["Pipeline", "Providers", "Prompts", "Dictionary", "Settings"]

_SHORTCUTS = """Keyboard shortcuts

Ctrl+1 to Ctrl+5   Jump to the Pipeline, Providers, Prompts, Dictionary or Settings tab
Ctrl+Tab           Next tab
Ctrl+Shift+Tab     Previous tab
Tab / Shift+Tab    Next / previous control
Alt+letter         The underlined letter on a button activates it
F6                 Move between the tab strip and the tab's contents
Ctrl+Q             Quit

On the Dictionary tab's entries table, arrow keys move between cells, Enter or F2
starts editing a cell, and clicking a row number selects the whole row so that
Remove selected entry can delete it."""


def apply_theme(window: wx.Window, theme: str) -> None:
    """Recursively override colours for `theme` in {"light", "dark"}; a no-op
    for "system", which just leaves the platform's own colours in place.

    Also a no-op under Windows High Contrast: that mode exists because the user
    picked specific colours for legibility, and an app that paints over them takes
    away the thing they turned it on for.
    """
    if theme not in ("light", "dark") or uses_high_contrast():
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

        self.notebook = wx.Notebook(self)
        describe(self.notebook, "SummaRibe sections")
        self.notebook.AddPage(PipelinePanel(self.notebook, self.settings_manager), _TABS[0])
        self.notebook.AddPage(ProviderEditorPanel(self.notebook), _TABS[1])
        self.notebook.AddPage(PromptEditorPanel(self.notebook), _TABS[2])
        self.notebook.AddPage(DictionaryEditorPanel(self.notebook), _TABS[3])
        self.notebook.AddPage(SettingsPanel(self.notebook, self.settings_manager), _TABS[4])

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self._build_menu_bar()

        self.CreateStatusBar()
        self.SetStatusText("Ready")

        apply_theme(self, gui_settings.theme)

        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _build_menu_bar(self) -> None:
        """A menu bar is the standard place a screen reader user looks first for what
        an app can do, and it is the only way to attach discoverable accelerators."""
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit\tCtrl+Q", "Close SummaRibe")
        self.Bind(wx.EVT_MENU, lambda _evt: self.Close(), exit_item)
        menu_bar.Append(file_menu, "&File")

        view_menu = wx.Menu()
        for index, tab in enumerate(_TABS):
            item = view_menu.Append(wx.ID_ANY, f"&{tab}\tCtrl+{index + 1}", f"Go to the {tab} tab")
            self.Bind(
                wx.EVT_MENU,
                lambda _evt, page=index: self._go_to_tab(page),
                item,
            )
        menu_bar.Append(view_menu, "&View")

        help_menu = wx.Menu()
        shortcuts_item = help_menu.Append(
            wx.ID_ANY, "&Keyboard shortcuts\tF1", "List the keyboard shortcuts"
        )
        self.Bind(
            wx.EVT_MENU,
            lambda _evt: wx.MessageBox(_SHORTCUTS, "SummaRibe - keyboard shortcuts"),
            shortcuts_item,
        )
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "About SummaRibe")
        self.Bind(
            wx.EVT_MENU,
            lambda _evt: wx.MessageBox(
                "SummaRibe downloads audio, transcribes it, and uses an AI provider "
                "to improve and summarize the transcript.",
                "About SummaRibe",
            ),
            about_item,
        )
        menu_bar.Append(help_menu, "&Help")

        self.SetMenuBar(menu_bar)

    def _go_to_tab(self, page: int) -> None:
        self.notebook.SetSelection(page)
        # Focus the tab itself rather than leaving it on the menu, so the screen
        # reader announces which tab is now current.
        self.notebook.SetFocus()
        self.SetStatusText(f"{_TABS[page]} tab")

    def _on_close(self, event: wx.CloseEvent) -> None:
        width, height = self.GetSize()
        settings = self.settings_manager.settings
        settings.gui.window_width = width
        settings.gui.window_height = height
        self.settings_manager.save(settings)
        event.Skip()

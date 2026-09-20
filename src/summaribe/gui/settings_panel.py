"""Settings tab: every customizable AppSettings field in one form."""

from __future__ import annotations

import wx

from summaribe.ai.prompts import PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.config import AppSettings, OutputFormat, SettingsManager
from summaribe.dictionary.filter import DictionaryStore
from summaribe.transcription.registry import list_provider_classes

_AUDIO_FORMATS = ["mp3", "wav", "flac", "m4a"]
_OUTPUT_FORMATS: list[OutputFormat] = ["txt", "srt", "vtt", "json"]
_THEMES = ["system", "light", "dark"]
_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


class SettingsPanel(wx.Panel):
    def __init__(self, parent: wx.Window, settings_manager: SettingsManager) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._build_ui()
        self._populate(settings_manager.settings)

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)
        scroller = wx.ScrolledWindow(self)
        scroller.SetScrollRate(0, 12)
        root = wx.BoxSizer(wx.VERTICAL)

        # General
        general = wx.StaticBoxSizer(wx.VERTICAL, scroller, "General")
        general_parent = general.GetStaticBox()
        grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        grid.AddGrowableCol(1, 1)
        self.work_dir_ctrl = wx.DirPickerCtrl(general_parent)
        self.audio_format_ctrl = wx.Choice(general_parent, choices=_AUDIO_FORMATS)
        self.audio_quality_ctrl = wx.SpinCtrl(general_parent, min=32, max=320)
        self.keep_intermediate_ctrl = wx.CheckBox(general_parent)
        self.output_formats_ctrl = wx.CheckListBox(general_parent, choices=_OUTPUT_FORMATS)
        self.log_level_ctrl = wx.Choice(general_parent, choices=_LOG_LEVELS)
        for label, ctrl in [
            ("Working directory", self.work_dir_ctrl),
            ("Audio format", self.audio_format_ctrl),
            ("Audio quality (kbps)", self.audio_quality_ctrl),
            ("Keep intermediate files", self.keep_intermediate_ctrl),
            ("Output formats", self.output_formats_ctrl),
            ("Log level", self.log_level_ctrl),
        ]:
            grid.Add(wx.StaticText(general_parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)
        general.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(general, 0, wx.EXPAND | wx.ALL, 8)

        # Transcription
        transcription = wx.StaticBoxSizer(wx.VERTICAL, scroller, "Transcription")
        transcription_parent = transcription.GetStaticBox()
        t_grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        t_grid.AddGrowableCol(1, 1)
        provider_ids = [cls.id for cls in list_provider_classes()]
        self.transcription_provider_ctrl = wx.Choice(transcription_parent, choices=provider_ids)
        self.transcription_model_ctrl = wx.TextCtrl(transcription_parent)
        self.transcription_model_path_ctrl = wx.FilePickerCtrl(transcription_parent)
        self.transcription_device_ctrl = wx.Choice(
            transcription_parent, choices=["auto", "cpu", "cuda"]
        )
        self.transcription_compute_type_ctrl = wx.TextCtrl(transcription_parent)
        self.transcription_language_ctrl = wx.TextCtrl(transcription_parent)
        self.transcription_language_ctrl.SetHint("blank = auto-detect")
        for label, ctrl in [
            ("Provider", self.transcription_provider_ctrl),
            ("Model (name or size)", self.transcription_model_ctrl),
            ("Custom model path (optional)", self.transcription_model_path_ctrl),
            ("Device", self.transcription_device_ctrl),
            ("Compute type", self.transcription_compute_type_ctrl),
            ("Language", self.transcription_language_ctrl),
        ]:
            t_grid.Add(
                wx.StaticText(transcription_parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL
            )
            t_grid.Add(ctrl, 1, wx.EXPAND)
        transcription.Add(t_grid, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(transcription, 0, wx.EXPAND | wx.ALL, 8)

        # AI
        ai = wx.StaticBoxSizer(wx.VERTICAL, scroller, "AI (improve & summarize)")
        ai_parent = ai.GetStaticBox()
        a_grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        a_grid.AddGrowableCol(1, 1)
        provider_choices = [p.id for p in ProviderStore().list()]
        improve_prompt_choices = [p.id for p in PromptStore().list_by_category("improve")]
        summarize_prompt_choices = [p.id for p in PromptStore().list_by_category("summarize")]
        self.improve_provider_ctrl = wx.Choice(ai_parent, choices=provider_choices)
        self.improve_prompt_ctrl = wx.Choice(ai_parent, choices=improve_prompt_choices)
        self.summarize_provider_ctrl = wx.Choice(ai_parent, choices=provider_choices)
        self.summarize_prompt_ctrl = wx.Choice(ai_parent, choices=summarize_prompt_choices)
        self.streaming_ctrl = wx.CheckBox(ai_parent)
        self.timeout_ctrl = wx.SpinCtrlDouble(ai_parent, min=1, max=3600, inc=1)
        self.temperature_ctrl = wx.SpinCtrlDouble(ai_parent, min=0, max=2, inc=0.1)
        self.max_tokens_ctrl = wx.SpinCtrl(ai_parent, min=1, max=200_000)

        self.improve_model_ctrl = wx.ComboBox(ai_parent, style=wx.CB_DROPDOWN)
        self.improve_model_ctrl.SetHint("blank = provider's own default")
        improve_fetch_btn = wx.Button(ai_parent, label="Fetch models")
        improve_fetch_btn.Bind(
            wx.EVT_BUTTON,
            lambda evt: self._on_fetch_models(self.improve_provider_ctrl, self.improve_model_ctrl),
        )
        improve_model_row = wx.BoxSizer(wx.HORIZONTAL)
        improve_model_row.Add(self.improve_model_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)
        improve_model_row.Add(improve_fetch_btn, 0)

        self.summarize_model_ctrl = wx.ComboBox(ai_parent, style=wx.CB_DROPDOWN)
        self.summarize_model_ctrl.SetHint("blank = provider's own default")
        summarize_fetch_btn = wx.Button(ai_parent, label="Fetch models")
        summarize_fetch_btn.Bind(
            wx.EVT_BUTTON,
            lambda evt: self._on_fetch_models(
                self.summarize_provider_ctrl, self.summarize_model_ctrl
            ),
        )
        summarize_model_row = wx.BoxSizer(wx.HORIZONTAL)
        summarize_model_row.Add(self.summarize_model_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)
        summarize_model_row.Add(summarize_fetch_btn, 0)

        for label, ctrl in [
            ("Improve provider", self.improve_provider_ctrl),
            ("Improve model", improve_model_row),
            ("Improve prompt", self.improve_prompt_ctrl),
            ("Summarize provider", self.summarize_provider_ctrl),
            ("Summarize model", summarize_model_row),
            ("Summarize prompt", self.summarize_prompt_ctrl),
            ("Streaming", self.streaming_ctrl),
            ("Timeout (s)", self.timeout_ctrl),
            ("Temperature", self.temperature_ctrl),
            ("Max tokens", self.max_tokens_ctrl),
        ]:
            a_grid.Add(wx.StaticText(ai_parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            a_grid.Add(ctrl, 1, wx.EXPAND)
        ai.Add(a_grid, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(ai, 0, wx.EXPAND | wx.ALL, 8)

        # Dictionary
        dictionary = wx.StaticBoxSizer(wx.VERTICAL, scroller, "Dictionary filter")
        dictionary_parent = dictionary.GetStaticBox()
        self.dictionary_enabled_ctrl = wx.CheckBox(dictionary_parent, label="Enabled")
        dictionary.Add(self.dictionary_enabled_ctrl, 0, wx.ALL, 5)
        dictionary_ids = [d.id for d in DictionaryStore().list()]
        self.dictionary_active_ctrl = wx.CheckListBox(dictionary_parent, choices=dictionary_ids)
        dictionary.Add(self.dictionary_active_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        root.Add(dictionary, 0, wx.EXPAND | wx.ALL, 8)

        # GUI
        gui = wx.StaticBoxSizer(wx.VERTICAL, scroller, "Interface")
        gui_parent = gui.GetStaticBox()
        g_grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        g_grid.AddGrowableCol(1, 1)
        self.theme_ctrl = wx.Choice(gui_parent, choices=_THEMES)
        self.auto_open_ctrl = wx.CheckBox(gui_parent)
        for label, ctrl in [
            ("Theme", self.theme_ctrl),
            ("Auto-open output folder", self.auto_open_ctrl),
        ]:
            g_grid.Add(wx.StaticText(gui_parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            g_grid.Add(ctrl, 1, wx.EXPAND)
        gui.Add(g_grid, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(gui, 0, wx.EXPAND | wx.ALL, 8)

        scroller.SetSizer(root)
        outer.Add(scroller, 1, wx.EXPAND)

        save_btn = wx.Button(self, label="Save settings")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        outer.Add(save_btn, 0, wx.ALL, 8)
        self.SetSizer(outer)

    def _populate(self, settings: AppSettings) -> None:
        self.work_dir_ctrl.SetPath(settings.work_dir)
        self.audio_format_ctrl.SetStringSelection(settings.audio_format)
        self.audio_quality_ctrl.SetValue(settings.audio_quality_kbps)
        self.keep_intermediate_ctrl.SetValue(settings.keep_intermediate_files)
        for index, fmt in enumerate(_OUTPUT_FORMATS):
            self.output_formats_ctrl.Check(index, fmt in settings.output_formats)
        self.log_level_ctrl.SetStringSelection(settings.log_level)

        t = settings.transcription
        self.transcription_provider_ctrl.SetStringSelection(t.default_provider)
        self.transcription_model_ctrl.SetValue(t.model)
        if t.model_path:
            self.transcription_model_path_ctrl.SetPath(t.model_path)
        self.transcription_device_ctrl.SetStringSelection(t.device)
        self.transcription_compute_type_ctrl.SetValue(t.compute_type)
        self.transcription_language_ctrl.SetValue(t.language or "")

        a = settings.ai
        self.improve_provider_ctrl.SetStringSelection(a.improve_provider_id)
        self.improve_model_ctrl.SetValue(a.improve_model or "")
        self.improve_prompt_ctrl.SetStringSelection(a.improve_prompt_id)
        self.summarize_provider_ctrl.SetStringSelection(a.summarize_provider_id)
        self.summarize_model_ctrl.SetValue(a.summarize_model or "")
        self.summarize_prompt_ctrl.SetStringSelection(a.summarize_prompt_id)
        self.streaming_ctrl.SetValue(a.streaming)
        self.timeout_ctrl.SetValue(a.timeout_seconds)
        self.temperature_ctrl.SetValue(a.temperature)
        self.max_tokens_ctrl.SetValue(a.max_tokens)

        d = settings.dictionary
        self.dictionary_enabled_ctrl.SetValue(d.enabled)
        for index in range(self.dictionary_active_ctrl.GetCount()):
            self.dictionary_active_ctrl.Check(
                index, self.dictionary_active_ctrl.GetString(index) in d.active_dictionary_ids
            )

        g = settings.gui
        self.theme_ctrl.SetStringSelection(g.theme)
        self.auto_open_ctrl.SetValue(g.auto_open_output_folder)

    def _on_save(self, _event: wx.CommandEvent) -> None:
        settings = self.settings_manager.settings
        settings.work_dir = self.work_dir_ctrl.GetPath() or settings.work_dir
        settings.audio_format = self.audio_format_ctrl.GetStringSelection() or settings.audio_format  # type: ignore[assignment]
        settings.audio_quality_kbps = self.audio_quality_ctrl.GetValue()
        settings.keep_intermediate_files = self.keep_intermediate_ctrl.GetValue()
        settings.output_formats = [
            fmt
            for index, fmt in enumerate(_OUTPUT_FORMATS)
            if self.output_formats_ctrl.IsChecked(index)
        ]
        settings.log_level = self.log_level_ctrl.GetStringSelection() or settings.log_level  # type: ignore[assignment]

        settings.transcription.default_provider = (
            self.transcription_provider_ctrl.GetStringSelection()
            or settings.transcription.default_provider
        )
        settings.transcription.model = self.transcription_model_ctrl.GetValue()
        settings.transcription.model_path = self.transcription_model_path_ctrl.GetPath() or None
        settings.transcription.device = (
            self.transcription_device_ctrl.GetStringSelection() or settings.transcription.device
        )
        settings.transcription.compute_type = self.transcription_compute_type_ctrl.GetValue()
        settings.transcription.language = (
            self.transcription_language_ctrl.GetValue().strip() or None
        )

        settings.ai.improve_provider_id = (
            self.improve_provider_ctrl.GetStringSelection() or settings.ai.improve_provider_id
        )
        settings.ai.improve_model = self.improve_model_ctrl.GetValue().strip() or None
        settings.ai.improve_prompt_id = (
            self.improve_prompt_ctrl.GetStringSelection() or settings.ai.improve_prompt_id
        )
        settings.ai.summarize_provider_id = (
            self.summarize_provider_ctrl.GetStringSelection() or settings.ai.summarize_provider_id
        )
        settings.ai.summarize_model = self.summarize_model_ctrl.GetValue().strip() or None
        settings.ai.summarize_prompt_id = (
            self.summarize_prompt_ctrl.GetStringSelection() or settings.ai.summarize_prompt_id
        )
        settings.ai.streaming = self.streaming_ctrl.GetValue()
        settings.ai.timeout_seconds = self.timeout_ctrl.GetValue()
        settings.ai.temperature = self.temperature_ctrl.GetValue()
        settings.ai.max_tokens = self.max_tokens_ctrl.GetValue()

        settings.dictionary.enabled = self.dictionary_enabled_ctrl.GetValue()
        settings.dictionary.active_dictionary_ids = [
            self.dictionary_active_ctrl.GetString(index)
            for index in range(self.dictionary_active_ctrl.GetCount())
            if self.dictionary_active_ctrl.IsChecked(index)
        ]

        settings.gui.theme = self.theme_ctrl.GetStringSelection() or settings.gui.theme  # type: ignore[assignment]
        settings.gui.auto_open_output_folder = self.auto_open_ctrl.GetValue()

        self.settings_manager.save(settings)
        wx.MessageBox("Settings saved.", "SummaRibe")

    def _on_fetch_models(self, provider_ctrl: wx.Choice, model_ctrl: wx.ComboBox) -> None:
        provider_id = provider_ctrl.GetStringSelection()
        if not provider_id:
            wx.MessageBox("Choose a provider first.", "SummaRibe", wx.ICON_WARNING)
            return
        store = ProviderStore()
        config = store.get(provider_id)
        if config.models is None:
            wx.MessageBox(
                f"Provider {provider_id!r} has no models listing endpoint configured.",
                "SummaRibe",
                wx.ICON_INFORMATION,
            )
            return
        try:
            model_ids = store.client_for(provider_id).list_models()
        except Exception as exc:
            wx.MessageBox(f"Could not fetch models: {exc}", "SummaRibe", wx.ICON_ERROR)
            return
        current = model_ctrl.GetValue()
        model_ctrl.Set(model_ids)
        model_ctrl.SetValue(current)

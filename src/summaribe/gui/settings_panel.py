"""Settings tab: every customizable AppSettings field in one form."""

from __future__ import annotations

import wx

from summaribe.ai.prompts import PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.config import AppSettings, OutputFormat, SettingsManager
from summaribe.dictionary.filter import DictionaryStore
from summaribe.gui.accessibility import add_labelled, describe
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
        describe(scroller, "Settings", "Scroll for more settings groups.")
        root = wx.BoxSizer(wx.VERTICAL)

        # General
        general = wx.StaticBoxSizer(wx.VERTICAL, scroller, "General")
        general_parent = general.GetStaticBox()
        grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        grid.AddGrowableCol(1, 1)
        self.work_dir_ctrl = add_labelled(
            grid,
            general_parent,
            "Working directory",
            wx.DirPickerCtrl,
            "Where downloads, transcripts and summaries are written.",
        )
        self.audio_format_ctrl = add_labelled(
            grid,
            general_parent,
            "Audio format",
            lambda p: wx.Choice(p, choices=_AUDIO_FORMATS),
            "Container the downloaded audio is converted to.",
        )
        self.audio_quality_ctrl = add_labelled(
            grid,
            general_parent,
            "Audio quality (kbps)",
            lambda p: wx.SpinCtrl(p, min=32, max=320),
            "Bitrate between 32 and 320 kbps.",
        )
        self.keep_intermediate_ctrl = add_labelled(
            grid,
            general_parent,
            "Keep intermediate files",
            wx.CheckBox,
            "Leave the downloaded audio and raw transcript on disk after a run.",
        )
        self.output_formats_ctrl = add_labelled(
            grid,
            general_parent,
            "Output formats",
            lambda p: wx.CheckListBox(p, choices=_OUTPUT_FORMATS),
            "Check every format the transcript should be written in.",
        )
        self.log_level_ctrl = add_labelled(
            grid, general_parent, "Log level", lambda p: wx.Choice(p, choices=_LOG_LEVELS)
        )
        general.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(general, 0, wx.EXPAND | wx.ALL, 8)

        # Transcription
        transcription = wx.StaticBoxSizer(wx.VERTICAL, scroller, "Transcription")
        transcription_parent = transcription.GetStaticBox()
        t_grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        t_grid.AddGrowableCol(1, 1)
        provider_ids = [cls.id for cls in list_provider_classes()]
        self.transcription_provider_ctrl = add_labelled(
            t_grid,
            transcription_parent,
            "Transcription provider",
            lambda p: wx.Choice(p, choices=provider_ids),
            "Speech-to-text backend used by the transcribe step.",
        )
        self.transcription_model_ctrl = add_labelled(
            t_grid,
            transcription_parent,
            "Transcription model (name or size)",
            wx.TextCtrl,
            "For example 'large-v3' for Whisper.",
        )
        self.transcription_model_path_ctrl = add_labelled(
            t_grid,
            transcription_parent,
            "Custom transcription model path",
            wx.FilePickerCtrl,
            "Optional. Overrides the model name with a file on disk.",
        )
        self.transcription_device_ctrl = add_labelled(
            t_grid,
            transcription_parent,
            "Transcription device",
            lambda p: wx.Choice(p, choices=["auto", "cpu", "cuda"]),
        )
        self.transcription_compute_type_ctrl = add_labelled(
            t_grid,
            transcription_parent,
            "Compute type",
            wx.TextCtrl,
            "Backend-specific precision, for example 'float16' or 'int8'.",
        )
        self.transcription_language_ctrl = add_labelled(
            t_grid,
            transcription_parent,
            "Transcription language",
            wx.TextCtrl,
            "Leave blank to auto-detect the spoken language.",
        )
        self.transcription_language_ctrl.SetHint("blank = auto-detect")
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

        self.improve_provider_ctrl = add_labelled(
            a_grid, ai_parent, "Improve provider", lambda p: wx.Choice(p, choices=provider_choices)
        )
        self.improve_model_ctrl = self._add_model_row(a_grid, ai_parent, "Improve model")
        self.improve_prompt_ctrl = add_labelled(
            a_grid,
            ai_parent,
            "Improve prompt",
            lambda p: wx.Choice(p, choices=improve_prompt_choices),
        )
        self.summarize_provider_ctrl = add_labelled(
            a_grid,
            ai_parent,
            "Summarize provider",
            lambda p: wx.Choice(p, choices=provider_choices),
        )
        self.summarize_model_ctrl = self._add_model_row(a_grid, ai_parent, "Summarize model")
        self.summarize_prompt_ctrl = add_labelled(
            a_grid,
            ai_parent,
            "Summarize prompt",
            lambda p: wx.Choice(p, choices=summarize_prompt_choices),
        )
        self.streaming_ctrl = add_labelled(
            a_grid,
            ai_parent,
            "Streaming",
            wx.CheckBox,
            "Receive the model's answer incrementally rather than in one response.",
        )
        self.timeout_ctrl = add_labelled(
            a_grid,
            ai_parent,
            "Timeout (seconds)",
            lambda p: wx.SpinCtrlDouble(p, min=1, max=3600, inc=1),
        )
        self.temperature_ctrl = add_labelled(
            a_grid,
            ai_parent,
            "Temperature",
            lambda p: wx.SpinCtrlDouble(p, min=0, max=2, inc=0.1),
            "0 is deterministic, 2 is most varied.",
        )
        self.max_tokens_ctrl = add_labelled(
            a_grid, ai_parent, "Max tokens", lambda p: wx.SpinCtrl(p, min=1, max=200_000)
        )
        ai.Add(a_grid, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(ai, 0, wx.EXPAND | wx.ALL, 8)

        # Dictionary
        dictionary = wx.StaticBoxSizer(wx.VERTICAL, scroller, "Dictionary filter")
        dictionary_parent = dictionary.GetStaticBox()
        self.dictionary_enabled_ctrl = wx.CheckBox(dictionary_parent, label="Dictionary filter on")
        describe(
            self.dictionary_enabled_ctrl,
            "Dictionary filter on",
            "Apply the checked dictionaries' find/replace rules to transcripts.",
        )
        dictionary.Add(self.dictionary_enabled_ctrl, 0, wx.ALL, 5)
        dictionary_ids = [d.id for d in DictionaryStore().list()]
        dictionary_label = wx.StaticText(dictionary_parent, label="Active dictionaries")
        self.dictionary_active_ctrl = wx.CheckListBox(dictionary_parent, choices=dictionary_ids)
        describe(
            self.dictionary_active_ctrl,
            "Active dictionaries",
            "Check each dictionary to apply. Empty until you create one on the Dictionary tab.",
        )
        dictionary.Add(dictionary_label, 0, wx.LEFT | wx.TOP, 5)
        dictionary.Add(self.dictionary_active_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        root.Add(dictionary, 0, wx.EXPAND | wx.ALL, 8)

        # GUI
        gui = wx.StaticBoxSizer(wx.VERTICAL, scroller, "Interface")
        gui_parent = gui.GetStaticBox()
        g_grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        g_grid.AddGrowableCol(1, 1)
        self.theme_ctrl = add_labelled(
            g_grid,
            gui_parent,
            "Theme",
            lambda p: wx.Choice(p, choices=_THEMES),
            "'system' follows your OS colours and is the only one that respects "
            "Windows High Contrast.",
        )
        self.auto_open_ctrl = add_labelled(
            g_grid,
            gui_parent,
            "Auto-open output folder",
            wx.CheckBox,
            "Open the working directory in your file manager when a run finishes.",
        )
        gui.Add(g_grid, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(gui, 0, wx.EXPAND | wx.ALL, 8)

        scroller.SetSizer(root)
        outer.Add(scroller, 1, wx.EXPAND)

        save_btn = wx.Button(self, label="&Save settings")
        describe(save_btn, "Save settings", "Write every field on this tab to the config file.")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        outer.Add(save_btn, 0, wx.ALL, 8)
        self.SetSizer(outer)

    def _add_model_row(self, grid: wx.Sizer, parent: wx.Window, label: str) -> wx.ComboBox:
        """A model combo box plus its "Fetch models" button, as one labelled grid row."""
        static = wx.StaticText(parent, label=label)
        model_ctrl = wx.ComboBox(parent, style=wx.CB_DROPDOWN)
        model_ctrl.SetHint("blank = provider's own default")
        describe(
            model_ctrl,
            label,
            "Type a model id, or leave blank to use the provider's own default. "
            "Use the Fetch models button to fill the list.",
        )
        fetch_btn = wx.Button(parent, label="Fetch models")
        describe(
            fetch_btn,
            f"Fetch models for {label.split(maxsplit=1)[0].lower()}",
            "Ask the selected provider which models it offers, and fill the list above.",
        )

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(model_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)
        row.Add(fetch_btn, 0)
        grid.Add(static, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(row, 1, wx.EXPAND)

        provider_ctrl_name = f"{label.split(maxsplit=1)[0].lower()}_provider_ctrl"
        fetch_btn.Bind(
            wx.EVT_BUTTON,
            lambda _evt: self._on_fetch_models(getattr(self, provider_ctrl_name), model_ctrl),
        )
        return model_ctrl

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
        wx.MessageBox(f"Fetched {len(model_ids)} models from {provider_id!r}.", "SummaRibe")

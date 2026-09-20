"""Pipeline tab: run any subset of steps, individually or chained, against a URL
or an existing local file, without blocking the UI thread.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from pathlib import Path

import wx

from summaribe.core.config import SettingsManager
from summaribe.core.pipeline import Pipeline, PipelineContext, PipelineStep
from summaribe.gui.accessibility import add_stacked, announce, describe
from summaribe.steps import DownloadStep, ImproveStep, SummarizeStep, TranscribeStep

STEP_CLASSES: dict[str, Callable[[], PipelineStep]] = {
    "download": DownloadStep,
    "transcribe": TranscribeStep,
    "improve": ImproveStep,
    "summarize": SummarizeStep,
}

_STEP_DESCRIPTIONS = {
    "download": "Fetch the audio for the URL above with yt-dlp.",
    "transcribe": "Turn the audio into a raw transcript with the configured speech-to-text model.",
    "improve": "Ask the AI provider to clean up punctuation and wording in the raw transcript.",
    "summarize": "Ask the AI provider for a summary of the transcript.",
}

EVT_PIPELINE_LOG = wx.NewEventType()
EVT_PIPELINE_DONE = wx.NewEventType()
PipelineLogEvent = wx.PyEventBinder(EVT_PIPELINE_LOG, 1)
PipelineDoneEvent = wx.PyEventBinder(EVT_PIPELINE_DONE, 1)


class _LogEvent(wx.PyCommandEvent):
    def __init__(self, message: str) -> None:
        super().__init__(EVT_PIPELINE_LOG, wx.ID_ANY)
        self.message = message


class _DoneEvent(wx.PyCommandEvent):
    def __init__(self, context: PipelineContext | None, error: str | None) -> None:
        super().__init__(EVT_PIPELINE_DONE, wx.ID_ANY)
        self.context = context
        self.error = error


class PipelinePanel(wx.Panel):
    def __init__(self, parent: wx.Window, settings_manager: SettingsManager) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._build_ui()
        self.Bind(PipelineLogEvent, self._on_log)
        self.Bind(PipelineDoneEvent, self._on_done)

    def _build_ui(self) -> None:
        root = wx.BoxSizer(wx.VERTICAL)

        input_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Input")
        input_parent = input_box.GetStaticBox()

        source_label = wx.StaticText(input_parent, label="Source URL or file path")
        self.source_ctrl = wx.TextCtrl(input_parent, value="")
        self.source_ctrl.SetHint("URL to download, or path to an existing audio/transcript file")
        describe(
            self.source_ctrl,
            "Source URL or file path",
            "Either a URL to download, or the path of an audio file or a .txt/.md transcript "
            "you already have.",
        )
        browse_btn = wx.Button(input_parent, label="&Browse file...")
        describe(
            browse_btn,
            "Browse for a source file",
            "Open a file dialog and put the chosen path in the source field.",
        )
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.source_ctrl, 1, wx.EXPAND | wx.RIGHT, 5)
        row.Add(browse_btn, 0)
        input_box.Add(source_label, 0, wx.LEFT | wx.TOP, 5)
        input_box.Add(row, 0, wx.EXPAND | wx.ALL, 5)

        self.work_dir_picker = add_stacked(
            input_box,
            input_parent,
            "Working directory for this run",
            lambda p: wx.DirPickerCtrl(
                p,
                path=self.settings_manager.settings.work_dir,
                message="Choose working directory",
            ),
            "Downloads, transcripts and summaries from this run are written here.",
            border=5,
        )
        root.Add(input_box, 0, wx.EXPAND | wx.ALL, 8)

        steps_box = wx.StaticBoxSizer(wx.HORIZONTAL, self, "Steps to run")
        steps_parent = steps_box.GetStaticBox()
        self.step_checks: dict[str, wx.CheckBox] = {}
        for step_name in STEP_CLASSES:
            label = step_name.capitalize()
            checkbox = wx.CheckBox(steps_parent, label=label)
            checkbox.SetValue(True)
            describe(checkbox, f"{label} step", _STEP_DESCRIPTIONS[step_name])
            steps_box.Add(checkbox, 0, wx.ALL, 5)
            self.step_checks[step_name] = checkbox
        root.Add(steps_box, 0, wx.EXPAND | wx.ALL, 8)

        run_row = wx.BoxSizer(wx.HORIZONTAL)
        self.run_btn = wx.Button(self, label="&Run")
        describe(self.run_btn, "Run", "Start the checked steps against the source above.")
        self.run_btn.Bind(wx.EVT_BUTTON, self._on_run)
        run_row.Add(self.run_btn, 0, wx.RIGHT, 8)

        # A named, focusable-by-screen-reader home for "what is happening right now",
        # so the state of a run is not conveyed by the disabled Run button alone.
        self.status_label = wx.StaticText(self, label="Ready")
        describe(self.status_label, "Ready")
        run_row.Add(self.status_label, 1, wx.ALIGN_CENTER_VERTICAL)
        root.Add(run_row, 0, wx.EXPAND | wx.ALL, 8)

        self.progress = wx.Gauge(self, style=wx.GA_HORIZONTAL)
        describe(self.progress, "Pipeline progress")
        self.progress.Hide()
        root.Add(self.progress, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self.log_ctrl = add_stacked(
            root,
            self,
            "Run log",
            lambda p: wx.TextCtrl(p, style=wx.TE_MULTILINE | wx.TE_READONLY),
            "Progress messages from each step, newest at the bottom. Read-only.",
            proportion=1,
        )

        results_label = wx.StaticText(self, label="Results")
        self.results = wx.Notebook(self)
        describe(self.results, "Results", "One tab per pipeline output.")
        self.raw_ctrl = wx.TextCtrl(self.results, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.improved_ctrl = wx.TextCtrl(self.results, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.summary_ctrl = wx.TextCtrl(self.results, style=wx.TE_MULTILINE | wx.TE_READONLY)
        describe(self.raw_ctrl, "Raw transcript", "Read-only output of the transcribe step.")
        describe(self.improved_ctrl, "Improved transcript", "Read-only output of the improve step.")
        describe(self.summary_ctrl, "Summary", "Read-only output of the summarize step.")
        self.results.AddPage(self.raw_ctrl, "Raw transcript")
        self.results.AddPage(self.improved_ctrl, "Improved transcript")
        self.results.AddPage(self.summary_ctrl, "Summary")
        root.Add(results_label, 0, wx.LEFT | wx.TOP, 8)
        root.Add(self.results, 1, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(root)

    def _set_status(self, message: str, *, notify: bool = True) -> None:
        """Update the status line. `notify` only for run-state changes, not every log
        line -- if a screen reader does honour the name-change event, per-line
        notifications would talk over whatever the user is reading."""
        self.status_label.SetLabel(message)
        if notify:
            announce(self.status_label, message)

    def _on_browse(self, _event: wx.CommandEvent) -> None:
        with wx.FileDialog(self, "Choose a file", style=wx.FD_OPEN) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.source_ctrl.SetValue(dialog.GetPath())

    def _on_run(self, _event: wx.CommandEvent) -> None:
        source = self.source_ctrl.GetValue().strip()
        if not source:
            wx.MessageBox("Enter a URL or choose a file first.", "SummaRibe", wx.ICON_WARNING)
            self.source_ctrl.SetFocus()
            return
        selected = [name for name, box in self.step_checks.items() if box.GetValue()]
        if not selected:
            wx.MessageBox("Select at least one step.", "SummaRibe", wx.ICON_WARNING)
            next(iter(self.step_checks.values())).SetFocus()
            return

        work_dir = Path(self.work_dir_picker.GetPath() or self.settings_manager.settings.work_dir)
        self.log_ctrl.Clear()
        self.raw_ctrl.Clear()
        self.improved_ctrl.Clear()
        self.summary_ctrl.Clear()
        self.run_btn.Disable()
        self.progress.Show()
        self.progress.Pulse()
        self.Layout()
        self._set_status(f"Running {len(selected)} steps...")

        thread = threading.Thread(
            target=self._run_pipeline_thread, args=(source, work_dir, selected), daemon=True
        )
        thread.start()

    def _run_pipeline_thread(self, source: str, work_dir: Path, selected: list[str]) -> None:
        try:
            context = PipelineContext(work_dir=work_dir, settings=self.settings_manager.settings)
            if "download" in selected:
                context.source_url = source
            else:
                path = Path(source)
                if path.suffix.lower() in {".txt", ".md"}:
                    context.transcript_raw = path.read_text(encoding="utf-8")
                else:
                    context.audio_path = path

            def on_progress(step_name: str, message: str) -> None:
                wx.PostEvent(self, _LogEvent(f"[{step_name}] {message}"))

            pipeline = Pipeline([STEP_CLASSES[name]() for name in selected])
            context = pipeline.run(context, on_progress=on_progress)
            wx.PostEvent(self, _DoneEvent(context, None))
        except Exception as exc:
            wx.PostEvent(self, _DoneEvent(None, f"{exc}\n{traceback.format_exc()}"))

    def _on_log(self, event: _LogEvent) -> None:
        self.log_ctrl.AppendText(event.message + "\n")
        self.progress.Pulse()
        self._set_status(event.message, notify=False)

    def _on_done(self, event: _DoneEvent) -> None:
        self.run_btn.Enable()
        self.progress.Hide()
        self.Layout()
        if event.error:
            self._set_status("Run failed.")
            # A modal dialog is the one notification every screen reader announces
            # reliably, so failures go through it rather than the status line alone.
            wx.MessageBox(event.error, "SummaRibe - step failed", wx.ICON_ERROR)
            self.run_btn.SetFocus()
            return
        context = event.context
        if context is None:
            return
        self.raw_ctrl.SetValue(context.transcript_raw or "")
        self.improved_ctrl.SetValue(context.transcript_improved or "")
        self.summary_ctrl.SetValue(context.summary or "")
        self.log_ctrl.AppendText("Done.\n")
        self._set_status("Done.")

        # Moving focus onto the filled-in result is the announcement: a screen reader
        # reads the newly focused tab and its contents, which no status text can force.
        pages = {self.raw_ctrl: 0, self.improved_ctrl: 1, self.summary_ctrl: 2}
        for ctrl in (self.summary_ctrl, self.improved_ctrl, self.raw_ctrl):
            if ctrl.GetValue():
                self.results.SetSelection(pages[ctrl])
                ctrl.SetFocus()
                break

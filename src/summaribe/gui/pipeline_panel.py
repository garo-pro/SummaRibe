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
from summaribe.steps import DownloadStep, ImproveStep, SummarizeStep, TranscribeStep

STEP_CLASSES: dict[str, Callable[[], PipelineStep]] = {
    "download": DownloadStep,
    "transcribe": TranscribeStep,
    "improve": ImproveStep,
    "summarize": SummarizeStep,
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
        self.source_ctrl = wx.TextCtrl(input_parent, value="")
        self.source_ctrl.SetHint("URL to download, or path to an existing audio/transcript file")
        browse_btn = wx.Button(input_parent, label="Browse file...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.source_ctrl, 1, wx.EXPAND | wx.RIGHT, 5)
        row.Add(browse_btn, 0)
        input_box.Add(row, 0, wx.EXPAND | wx.ALL, 5)

        self.work_dir_picker = wx.DirPickerCtrl(
            input_parent,
            path=self.settings_manager.settings.work_dir,
            message="Choose working directory",
        )
        input_box.Add(self.work_dir_picker, 0, wx.EXPAND | wx.ALL, 5)
        root.Add(input_box, 0, wx.EXPAND | wx.ALL, 8)

        steps_box = wx.StaticBoxSizer(wx.HORIZONTAL, self, "Steps to run")
        steps_parent = steps_box.GetStaticBox()
        self.step_checks: dict[str, wx.CheckBox] = {}
        for step_name in STEP_CLASSES:
            checkbox = wx.CheckBox(steps_parent, label=step_name.capitalize())
            checkbox.SetValue(True)
            steps_box.Add(checkbox, 0, wx.ALL, 5)
            self.step_checks[step_name] = checkbox
        root.Add(steps_box, 0, wx.EXPAND | wx.ALL, 8)

        self.run_btn = wx.Button(self, label="Run")
        self.run_btn.Bind(wx.EVT_BUTTON, self._on_run)
        root.Add(self.run_btn, 0, wx.ALL, 8)

        self.log_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        root.Add(self.log_ctrl, 1, wx.EXPAND | wx.ALL, 8)

        self.results = wx.Notebook(self)
        self.raw_ctrl = wx.TextCtrl(self.results, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.improved_ctrl = wx.TextCtrl(self.results, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.summary_ctrl = wx.TextCtrl(self.results, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.results.AddPage(self.raw_ctrl, "Raw transcript")
        self.results.AddPage(self.improved_ctrl, "Improved transcript")
        self.results.AddPage(self.summary_ctrl, "Summary")
        root.Add(self.results, 1, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(root)

    def _on_browse(self, _event: wx.CommandEvent) -> None:
        with wx.FileDialog(self, "Choose a file", style=wx.FD_OPEN) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.source_ctrl.SetValue(dialog.GetPath())

    def _on_run(self, _event: wx.CommandEvent) -> None:
        source = self.source_ctrl.GetValue().strip()
        if not source:
            wx.MessageBox("Enter a URL or choose a file first.", "SummaRibe", wx.ICON_WARNING)
            return
        selected = [name for name, box in self.step_checks.items() if box.GetValue()]
        if not selected:
            wx.MessageBox("Select at least one step.", "SummaRibe", wx.ICON_WARNING)
            return

        work_dir = Path(self.work_dir_picker.GetPath() or self.settings_manager.settings.work_dir)
        self.log_ctrl.Clear()
        self.raw_ctrl.Clear()
        self.improved_ctrl.Clear()
        self.summary_ctrl.Clear()
        self.run_btn.Disable()

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

    def _on_done(self, event: _DoneEvent) -> None:
        self.run_btn.Enable()
        if event.error:
            wx.MessageBox(event.error, "SummaRibe - step failed", wx.ICON_ERROR)
            return
        context = event.context
        if context is None:
            return
        self.raw_ctrl.SetValue(context.transcript_raw or "")
        self.improved_ctrl.SetValue(context.transcript_improved or "")
        self.summary_ctrl.SetValue(context.summary or "")
        self.log_ctrl.AppendText("Done.\n")

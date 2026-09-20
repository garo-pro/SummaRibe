"""Prompts tab: create/edit/delete system prompts for improve and summarize steps."""

from __future__ import annotations

import uuid

import wx

from summaribe.ai.prompts import PromptStore, SystemPrompt
from summaribe.core.exceptions import ConfigError, RegistryError
from summaribe.gui.accessibility import add_labelled, add_stacked, describe


class PromptEditorPanel(wx.Panel):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.store = PromptStore()
        self._build_ui()
        self._reload_list()

    def _build_ui(self) -> None:
        root = wx.BoxSizer(wx.HORIZONTAL)

        left = wx.BoxSizer(wx.VERTICAL)
        list_label = wx.StaticText(self, label="Prompts")
        self.list_box = wx.ListBox(self, size=(240, -1))
        describe(
            self.list_box,
            "Prompts",
            "Select a prompt to load it into the form on the right.",
        )
        self.list_box.Bind(wx.EVT_LISTBOX, self._on_select)
        left.Add(list_label, 0, wx.LEFT | wx.TOP, 5)
        left.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 5)
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        new_btn = wx.Button(self, label="&New")
        describe(new_btn, "New prompt", "Fill the form with a blank prompt and a fresh id.")
        new_btn.Bind(wx.EVT_BUTTON, self._on_new)
        delete_btn = wx.Button(self, label="&Delete")
        describe(delete_btn, "Delete prompt", "Delete the prompt selected in the list.")
        delete_btn.Bind(wx.EVT_BUTTON, self._on_delete)
        btn_row.Add(new_btn, 0, wx.RIGHT, 5)
        btn_row.Add(delete_btn, 0)
        left.Add(btn_row, 0, wx.ALL, 5)
        root.Add(left, 0, wx.EXPAND)

        right = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        grid.AddGrowableCol(1, 1)

        self.id_ctrl = add_labelled(
            grid, self, "Prompt id", wx.TextCtrl, "Unique identifier used in settings and the CLI."
        )
        self.name_ctrl = add_labelled(
            grid, self, "Prompt name", wx.TextCtrl, "Human-readable name."
        )
        self.category_ctrl = add_labelled(
            grid,
            self,
            "Category",
            lambda p: wx.Choice(p, choices=["improve", "summarize"]),
            "Which pipeline step this prompt can be selected for.",
        )
        self.description_ctrl = add_labelled(grid, self, "Prompt description", wx.TextCtrl)
        right.Add(grid, 0, wx.EXPAND | wx.ALL, 8)

        self.content_ctrl = add_stacked(
            right,
            self,
            "Prompt content",
            lambda p: wx.TextCtrl(p, style=wx.TE_MULTILINE, size=(-1, 260)),
            "The system prompt text sent to the AI provider.",
            proportion=1,
        )

        save_btn = wx.Button(self, label="&Save")
        describe(save_btn, "Save prompt", "Write the form above to disk.")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        right.Add(save_btn, 0, wx.ALL, 8)

        root.Add(right, 1, wx.EXPAND)
        self.SetSizer(root)

    def _reload_list(self, select_id: str | None = None) -> None:
        self.list_box.Clear()
        for prompt in self.store.list():
            self.list_box.Append(f"[{prompt.category}] {prompt.name} ({prompt.id})", prompt.id)
        if select_id:
            for index in range(self.list_box.GetCount()):
                if self.list_box.GetClientData(index) == select_id:
                    self.list_box.SetSelection(index)
                    self._populate(self.store.get(select_id))
                    break

    def _on_select(self, _event: wx.CommandEvent) -> None:
        index = self.list_box.GetSelection()
        if index == wx.NOT_FOUND:
            return
        self._populate(self.store.get(self.list_box.GetClientData(index)))

    def _populate(self, prompt: SystemPrompt) -> None:
        self.id_ctrl.SetValue(prompt.id)
        self.name_ctrl.SetValue(prompt.name)
        self.category_ctrl.SetStringSelection(prompt.category)
        self.description_ctrl.SetValue(prompt.description)
        self.content_ctrl.SetValue(prompt.content)

    def _on_new(self, _event: wx.CommandEvent) -> None:
        self.list_box.SetSelection(wx.NOT_FOUND)
        self._populate(
            SystemPrompt(
                id=f"custom-{uuid.uuid4().hex[:8]}",
                name="New prompt",
                category="improve",
                content="",
            )
        )
        self.name_ctrl.SetFocus()

    def _on_delete(self, _event: wx.CommandEvent) -> None:
        index = self.list_box.GetSelection()
        if index == wx.NOT_FOUND:
            wx.MessageBox("Select a prompt to delete first.", "SummaRibe", wx.ICON_WARNING)
            self.list_box.SetFocus()
            return
        prompt_id = self.list_box.GetClientData(index)
        try:
            self.store.delete(prompt_id)
        except (ConfigError, RegistryError) as exc:
            wx.MessageBox(str(exc), "SummaRibe", wx.ICON_ERROR)
            return
        self._reload_list()
        self.list_box.SetFocus()

    def _on_save(self, _event: wx.CommandEvent) -> None:
        category = self.category_ctrl.GetStringSelection() or "improve"
        prompt = SystemPrompt(
            id=self.id_ctrl.GetValue().strip(),
            name=self.name_ctrl.GetValue().strip(),
            category=category,  # type: ignore[arg-type]
            description=self.description_ctrl.GetValue(),
            content=self.content_ctrl.GetValue(),
        )
        self.store.save(prompt)
        self._reload_list(select_id=prompt.id)
        wx.MessageBox(f"Saved prompt {prompt.id!r}.", "SummaRibe")

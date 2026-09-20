"""Providers tab: create/edit/delete AI provider configs (see ai.schema.ProviderConfig).

Structured fields cover the common cases; ``headers``, ``request_template`` and
``variables`` are edited as raw JSON text since they are themselves nested,
free-form templates.
"""

from __future__ import annotations

import json
import uuid

import wx

from summaribe.ai.registry import ProviderStore
from summaribe.ai.schema import ProviderConfig
from summaribe.core.exceptions import ConfigError, RegistryError
from summaribe.gui.accessibility import add_labelled, add_stacked, describe


class ProviderEditorPanel(wx.Panel):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.store = ProviderStore()
        self._build_ui()
        self._reload_list()

    def _build_ui(self) -> None:
        root = wx.BoxSizer(wx.HORIZONTAL)

        left = wx.BoxSizer(wx.VERTICAL)
        list_label = wx.StaticText(self, label="Providers")
        self.list_box = wx.ListBox(self, size=(220, -1))
        describe(
            self.list_box,
            "Providers",
            "Select a provider to load it into the form on the right.",
        )
        self.list_box.Bind(wx.EVT_LISTBOX, self._on_select)
        left.Add(list_label, 0, wx.LEFT | wx.TOP, 5)
        left.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 5)
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        new_btn = wx.Button(self, label="&New")
        describe(new_btn, "New provider", "Fill the form with a blank provider and a fresh id.")
        new_btn.Bind(wx.EVT_BUTTON, self._on_new)
        delete_btn = wx.Button(self, label="&Delete")
        describe(delete_btn, "Delete provider", "Delete the provider selected in the list.")
        delete_btn.Bind(wx.EVT_BUTTON, self._on_delete)
        btn_row.Add(new_btn, 0, wx.RIGHT, 5)
        btn_row.Add(delete_btn, 0)
        left.Add(btn_row, 0, wx.ALL, 5)
        root.Add(left, 0, wx.EXPAND)

        right = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        grid.AddGrowableCol(1, 1)

        self.id_ctrl = add_labelled(
            grid,
            self,
            "Provider id",
            wx.TextCtrl,
            "Unique identifier used in settings and the CLI.",
        )
        self.name_ctrl = add_labelled(
            grid, self, "Provider name", wx.TextCtrl, "Human-readable name."
        )
        self.description_ctrl = add_labelled(grid, self, "Provider description", wx.TextCtrl)
        self.base_url_ctrl = add_labelled(
            grid,
            self,
            "Base URL",
            wx.TextCtrl,
            "Scheme and host, for example https://api.example.com",
        )
        self.endpoint_ctrl = add_labelled(
            grid,
            self,
            "Endpoint",
            wx.TextCtrl,
            "Path appended to the base URL, for example /v1/chat/completions",
        )
        self.method_ctrl = add_labelled(
            grid, self, "HTTP method", lambda p: wx.Choice(p, choices=["POST", "GET"])
        )
        self.api_key_env_ctrl = add_labelled(
            grid,
            self,
            "API key environment variable",
            wx.TextCtrl,
            "Name of the environment variable holding the key. The key itself is never "
            "stored in this config.",
        )
        self.timeout_ctrl = add_labelled(
            grid, self, "Timeout (seconds)", lambda p: wx.SpinCtrlDouble(p, min=1, max=3600, inc=1)
        )
        self.stream_ctrl = add_labelled(
            grid, self, "Stream", wx.CheckBox, "Whether this provider streams its response."
        )
        self.stream_format_ctrl = add_labelled(
            grid,
            self,
            "Stream format",
            lambda p: wx.Choice(p, choices=["sse", "ndjson"]),
            "Wire format of the streamed response.",
        )
        self.response_path_ctrl = add_labelled(
            grid,
            self,
            "Response path",
            wx.TextCtrl,
            "Dotted path to the text in a non-streamed reply, for example "
            "choices.0.message.content",
        )
        self.stream_delta_path_ctrl = add_labelled(
            grid, self, "Stream delta path", wx.TextCtrl, "Dotted path to each streamed chunk."
        )
        self.stream_done_path_ctrl = add_labelled(
            grid, self, "Stream done path", wx.TextCtrl, "Dotted path to the end-of-stream marker."
        )
        right.Add(grid, 0, wx.EXPAND | wx.ALL, 8)

        self.headers_ctrl = add_stacked(
            right,
            self,
            "Headers (JSON object)",
            lambda p: wx.TextCtrl(p, style=wx.TE_MULTILINE, size=(-1, 60)),
            "Extra HTTP headers, as a JSON object.",
        )
        self.request_template_ctrl = add_stacked(
            right,
            self,
            "Request template (JSON)",
            lambda p: wx.TextCtrl(p, style=wx.TE_MULTILINE, size=(-1, 140)),
            "Request body as JSON, with {{variable}} placeholders.",
            proportion=1,
        )
        self.variables_ctrl = add_stacked(
            right,
            self,
            "Default variables (JSON)",
            lambda p: wx.TextCtrl(p, style=wx.TE_MULTILINE, size=(-1, 60)),
            "Default values for the placeholders used in the request template.",
        )

        save_btn = wx.Button(self, label="&Save")
        describe(save_btn, "Save provider", "Write the form above to disk.")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        right.Add(save_btn, 0, wx.ALL, 8)

        root.Add(right, 1, wx.EXPAND)
        self.SetSizer(root)

    def _reload_list(self, select_id: str | None = None) -> None:
        self.list_box.Clear()
        self._providers = self.store.list()
        for provider in self._providers:
            self.list_box.Append(f"{provider.name} ({provider.id})", provider.id)
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
        provider_id = self.list_box.GetClientData(index)
        self._populate(self.store.get(provider_id))

    def _populate(self, provider: ProviderConfig) -> None:
        self.id_ctrl.SetValue(provider.id)
        self.name_ctrl.SetValue(provider.name)
        self.description_ctrl.SetValue(provider.description)
        self.base_url_ctrl.SetValue(provider.base_url)
        self.endpoint_ctrl.SetValue(provider.endpoint)
        self.method_ctrl.SetStringSelection(provider.method)
        self.api_key_env_ctrl.SetValue(provider.api_key_env or "")
        self.timeout_ctrl.SetValue(provider.timeout_seconds)
        self.stream_ctrl.SetValue(provider.stream)
        self.stream_format_ctrl.SetStringSelection(provider.stream_format)
        self.response_path_ctrl.SetValue(provider.response_path)
        self.stream_delta_path_ctrl.SetValue(provider.stream_delta_path or "")
        self.stream_done_path_ctrl.SetValue(provider.stream_done_path or "")
        self.headers_ctrl.SetValue(json.dumps(provider.headers, indent=2))
        self.request_template_ctrl.SetValue(json.dumps(provider.request_template, indent=2))
        self.variables_ctrl.SetValue(json.dumps(provider.variables, indent=2))

    def _on_new(self, _event: wx.CommandEvent) -> None:
        self.list_box.SetSelection(wx.NOT_FOUND)
        blank = ProviderConfig(
            id=f"custom-{uuid.uuid4().hex[:8]}",
            name="New provider",
            base_url="http://localhost:8080",
            endpoint="/v1/chat/completions",
            request_template={
                "model": "{{model}}",
                "messages": "{{messages}}",
                "temperature": "{{temperature}}",
                "stream": "{{stream}}",
            },
            response_path="choices.0.message.content",
            variables={"model": "model-name", "temperature": 0.3, "max_tokens": 2048},
        )
        self._populate(blank)
        self.name_ctrl.SetFocus()

    def _on_delete(self, _event: wx.CommandEvent) -> None:
        index = self.list_box.GetSelection()
        if index == wx.NOT_FOUND:
            wx.MessageBox("Select a provider to delete first.", "SummaRibe", wx.ICON_WARNING)
            self.list_box.SetFocus()
            return
        provider_id = self.list_box.GetClientData(index)
        try:
            self.store.delete(provider_id)
        except (ConfigError, RegistryError) as exc:
            wx.MessageBox(str(exc), "SummaRibe", wx.ICON_ERROR)
            return
        self._reload_list()
        self.list_box.SetFocus()

    def _on_save(self, _event: wx.CommandEvent) -> None:
        try:
            config = ProviderConfig(
                id=self.id_ctrl.GetValue().strip(),
                name=self.name_ctrl.GetValue().strip(),
                description=self.description_ctrl.GetValue(),
                base_url=self.base_url_ctrl.GetValue().strip(),
                endpoint=self.endpoint_ctrl.GetValue().strip(),
                method=self.method_ctrl.GetStringSelection() or "POST",
                headers=json.loads(self.headers_ctrl.GetValue() or "{}"),
                api_key_env=self.api_key_env_ctrl.GetValue().strip() or None,
                timeout_seconds=self.timeout_ctrl.GetValue(),
                stream=self.stream_ctrl.GetValue(),
                stream_format=self.stream_format_ctrl.GetStringSelection() or "sse",
                request_template=json.loads(self.request_template_ctrl.GetValue() or "{}"),
                response_path=self.response_path_ctrl.GetValue().strip(),
                stream_delta_path=self.stream_delta_path_ctrl.GetValue().strip() or None,
                stream_done_path=self.stream_done_path_ctrl.GetValue().strip() or None,
                variables=json.loads(self.variables_ctrl.GetValue() or "{}"),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            wx.MessageBox(f"Invalid provider config: {exc}", "SummaRibe", wx.ICON_ERROR)
            return
        self.store.save(config)
        self._reload_list(select_id=config.id)
        wx.MessageBox(f"Saved provider {config.id!r}.", "SummaRibe")

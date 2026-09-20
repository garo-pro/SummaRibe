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


class ProviderEditorPanel(wx.Panel):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.store = ProviderStore()
        self._build_ui()
        self._reload_list()

    def _build_ui(self) -> None:
        root = wx.BoxSizer(wx.HORIZONTAL)

        left = wx.BoxSizer(wx.VERTICAL)
        self.list_box = wx.ListBox(self, size=(220, -1))
        self.list_box.Bind(wx.EVT_LISTBOX, self._on_select)
        left.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 5)
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        new_btn = wx.Button(self, label="New")
        new_btn.Bind(wx.EVT_BUTTON, self._on_new)
        delete_btn = wx.Button(self, label="Delete")
        delete_btn.Bind(wx.EVT_BUTTON, self._on_delete)
        btn_row.Add(new_btn, 0, wx.RIGHT, 5)
        btn_row.Add(delete_btn, 0)
        left.Add(btn_row, 0, wx.ALL, 5)
        root.Add(left, 0, wx.EXPAND)

        right = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        grid.AddGrowableCol(1, 1)

        self.id_ctrl = wx.TextCtrl(self)
        self.name_ctrl = wx.TextCtrl(self)
        self.description_ctrl = wx.TextCtrl(self)
        self.base_url_ctrl = wx.TextCtrl(self)
        self.endpoint_ctrl = wx.TextCtrl(self)
        self.method_ctrl = wx.Choice(self, choices=["POST", "GET"])
        self.api_key_env_ctrl = wx.TextCtrl(self)
        self.timeout_ctrl = wx.SpinCtrlDouble(self, min=1, max=3600, inc=1)
        self.stream_ctrl = wx.CheckBox(self)
        self.stream_format_ctrl = wx.Choice(self, choices=["sse", "ndjson"])
        self.response_path_ctrl = wx.TextCtrl(self)
        self.stream_delta_path_ctrl = wx.TextCtrl(self)
        self.stream_done_path_ctrl = wx.TextCtrl(self)

        for label, ctrl in [
            ("Id", self.id_ctrl),
            ("Name", self.name_ctrl),
            ("Description", self.description_ctrl),
            ("Base URL", self.base_url_ctrl),
            ("Endpoint", self.endpoint_ctrl),
            ("Method", self.method_ctrl),
            ("API key env var", self.api_key_env_ctrl),
            ("Timeout (s)", self.timeout_ctrl),
            ("Stream", self.stream_ctrl),
            ("Stream format", self.stream_format_ctrl),
            ("Response path", self.response_path_ctrl),
            ("Stream delta path", self.stream_delta_path_ctrl),
            ("Stream done path", self.stream_done_path_ctrl),
        ]:
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)
        right.Add(grid, 0, wx.EXPAND | wx.ALL, 8)

        right.Add(wx.StaticText(self, label="Headers (JSON object)"), 0, wx.LEFT | wx.TOP, 8)
        self.headers_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 60))
        right.Add(self.headers_ctrl, 0, wx.EXPAND | wx.ALL, 8)

        right.Add(wx.StaticText(self, label="Request template (JSON)"), 0, wx.LEFT, 8)
        self.request_template_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 140))
        right.Add(self.request_template_ctrl, 1, wx.EXPAND | wx.ALL, 8)

        right.Add(wx.StaticText(self, label="Default variables (JSON)"), 0, wx.LEFT, 8)
        self.variables_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 60))
        right.Add(self.variables_ctrl, 0, wx.EXPAND | wx.ALL, 8)

        save_btn = wx.Button(self, label="Save")
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

    def _on_delete(self, _event: wx.CommandEvent) -> None:
        index = self.list_box.GetSelection()
        if index == wx.NOT_FOUND:
            return
        provider_id = self.list_box.GetClientData(index)
        try:
            self.store.delete(provider_id)
        except (ConfigError, RegistryError) as exc:
            wx.MessageBox(str(exc), "SummaRibe", wx.ICON_ERROR)
            return
        self._reload_list()

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

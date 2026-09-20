"""Dictionary tab: create/edit/delete word-replacement dictionaries.

No dictionaries ship by default; this tab exists purely for user-authored
find/replace rules (e.g. jargon or names the transcription model mishears).
"""

from __future__ import annotations

import uuid

import wx
import wx.grid as gridlib

from summaribe.core.exceptions import RegistryError
from summaribe.dictionary.filter import Dictionary, DictionaryEntry, DictionaryStore
from summaribe.gui.accessibility import add_labelled, describe

_COLUMNS = ["Find", "Replace", "Case sensitive", "Whole word"]

# wxGrid's accessibility support reads a cell out by its string value, and the
# boolean columns' default values are "1" and "" -- announced as "1" and silence.
# Naming them makes an unchecked cell say something.
_TRUE = "yes"
_FALSE = "no"


class DictionaryEditorPanel(wx.Panel):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.store = DictionaryStore()
        self._build_ui()
        self._reload_list()

    def _build_ui(self) -> None:
        gridlib.GridCellBoolEditor.UseStringValues(_TRUE, _FALSE)
        root = wx.BoxSizer(wx.HORIZONTAL)

        left = wx.BoxSizer(wx.VERTICAL)
        list_label = wx.StaticText(self, label="Dictionaries")
        self.list_box = wx.ListBox(self, size=(220, -1))
        describe(
            self.list_box,
            "Dictionaries",
            "Select a dictionary to load it into the editor on the right. "
            "Empty until you create one.",
        )
        self.list_box.Bind(wx.EVT_LISTBOX, self._on_select)
        left.Add(list_label, 0, wx.LEFT | wx.TOP, 5)
        left.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 5)
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        new_btn = wx.Button(self, label="&New")
        describe(new_btn, "New dictionary", "Fill the editor with a blank dictionary.")
        new_btn.Bind(wx.EVT_BUTTON, self._on_new)
        delete_btn = wx.Button(self, label="&Delete")
        describe(delete_btn, "Delete dictionary", "Delete the dictionary selected in the list.")
        delete_btn.Bind(wx.EVT_BUTTON, self._on_delete)
        btn_row.Add(new_btn, 0, wx.RIGHT, 5)
        btn_row.Add(delete_btn, 0)
        left.Add(btn_row, 0, wx.ALL, 5)
        root.Add(left, 0, wx.EXPAND)

        right = wx.BoxSizer(wx.VERTICAL)
        header_grid = wx.FlexGridSizer(cols=2, gap=(6, 6))
        header_grid.AddGrowableCol(1, 1)
        self.id_ctrl = add_labelled(
            header_grid, self, "Dictionary id", wx.TextCtrl, "Unique identifier."
        )
        self.name_ctrl = add_labelled(
            header_grid, self, "Dictionary name", wx.TextCtrl, "Human-readable name."
        )
        self.description_ctrl = add_labelled(
            header_grid, self, "Dictionary description", wx.TextCtrl
        )
        right.Add(header_grid, 0, wx.EXPAND | wx.ALL, 8)

        entries_label = wx.StaticText(self, label="Replacement entries")
        self.grid = gridlib.Grid(self)
        self.grid.CreateGrid(0, len(_COLUMNS))
        # A native header is a real Win32 header control, so screen readers can read
        # the column names; wxGrid's own drawn header is just pixels.
        self.grid.UseNativeColHeader(True)
        for index, name in enumerate(_COLUMNS):
            self.grid.SetColLabelValue(index, name)
        # wxGrid supplies its own wxAccessible (wxWidgets 3.3+), which reports each
        # cell's row, column and value -- so unlike every other control here it must
        # keep that accessible rather than be given a flat name.
        self.grid.SetToolTip(
            "Each row is one find/replace rule. Case sensitive and Whole word are "
            f"{_TRUE} or {_FALSE}."
        )
        right.Add(entries_label, 0, wx.LEFT | wx.TOP, 8)
        right.Add(self.grid, 1, wx.EXPAND | wx.ALL, 8)

        row_btns = wx.BoxSizer(wx.HORIZONTAL)
        add_row_btn = wx.Button(self, label="&Add entry")
        describe(add_row_btn, "Add entry", "Append an empty row to the entries table.")
        add_row_btn.Bind(wx.EVT_BUTTON, self._on_add_row)
        remove_row_btn = wx.Button(self, label="&Remove selected entry")
        describe(
            remove_row_btn,
            "Remove selected entry",
            "Delete the rows selected in the entries table.",
        )
        remove_row_btn.Bind(wx.EVT_BUTTON, self._on_remove_row)
        row_btns.Add(add_row_btn, 0, wx.RIGHT, 5)
        row_btns.Add(remove_row_btn, 0)
        right.Add(row_btns, 0, wx.ALL, 8)

        save_btn = wx.Button(self, label="&Save")
        describe(save_btn, "Save dictionary", "Write the editor above to disk.")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        right.Add(save_btn, 0, wx.ALL, 8)

        root.Add(right, 1, wx.EXPAND)
        self.SetSizer(root)

    def _reload_list(self, select_id: str | None = None) -> None:
        self.list_box.Clear()
        for dictionary in self.store.list():
            self.list_box.Append(f"{dictionary.name} ({dictionary.id})", dictionary.id)
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

    def _clear_grid(self) -> None:
        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())

    def _populate(self, dictionary: Dictionary) -> None:
        self.id_ctrl.SetValue(dictionary.id)
        self.name_ctrl.SetValue(dictionary.name)
        self.description_ctrl.SetValue(dictionary.description)
        self._clear_grid()
        for entry in dictionary.entries:
            self._append_row(entry)

    def _append_row(self, entry: DictionaryEntry | None = None) -> None:
        row = self.grid.GetNumberRows()
        self.grid.AppendRows(1)
        entry = entry or DictionaryEntry(find="", replace="")
        self.grid.SetCellValue(row, 0, entry.find)
        self.grid.SetCellValue(row, 1, entry.replace)
        for column, flag in ((2, entry.case_sensitive), (3, entry.whole_word)):
            self.grid.SetCellValue(row, column, _TRUE if flag else _FALSE)
            self.grid.SetCellRenderer(row, column, gridlib.GridCellBoolRenderer())
            self.grid.SetCellEditor(row, column, gridlib.GridCellBoolEditor())

    def _on_add_row(self, _event: wx.CommandEvent) -> None:
        self._append_row()
        # Put the caret in the new row's first cell, so the screen reader lands
        # where the user is meant to type rather than leaving them to hunt for it.
        self.grid.SetFocus()
        self.grid.SetGridCursor(self.grid.GetNumberRows() - 1, 0)
        self.grid.MakeCellVisible(self.grid.GetNumberRows() - 1, 0)

    def _on_remove_row(self, _event: wx.CommandEvent) -> None:
        rows = sorted(set(self.grid.GetSelectedRows()), reverse=True)
        if not rows:
            wx.MessageBox(
                "Select whole rows in the entries table first.", "SummaRibe", wx.ICON_WARNING
            )
            self.grid.SetFocus()
            return
        for row in rows:
            self.grid.DeleteRows(row, 1)
        self.grid.SetFocus()

    def _on_new(self, _event: wx.CommandEvent) -> None:
        self.list_box.SetSelection(wx.NOT_FOUND)
        self._populate(Dictionary(id=f"custom-{uuid.uuid4().hex[:8]}", name="New dictionary"))
        self.name_ctrl.SetFocus()

    def _on_delete(self, _event: wx.CommandEvent) -> None:
        index = self.list_box.GetSelection()
        if index == wx.NOT_FOUND:
            wx.MessageBox("Select a dictionary to delete first.", "SummaRibe", wx.ICON_WARNING)
            self.list_box.SetFocus()
            return
        dictionary_id = self.list_box.GetClientData(index)
        try:
            self.store.delete(dictionary_id)
        except RegistryError as exc:
            wx.MessageBox(str(exc), "SummaRibe", wx.ICON_ERROR)
            return
        self._reload_list()
        self.list_box.SetFocus()

    def _on_save(self, _event: wx.CommandEvent) -> None:
        entries = []
        for row in range(self.grid.GetNumberRows()):
            find = self.grid.GetCellValue(row, 0).strip()
            if not find:
                continue
            entries.append(
                DictionaryEntry(
                    find=find,
                    replace=self.grid.GetCellValue(row, 1),
                    case_sensitive=self.grid.GetCellValue(row, 2) == _TRUE,
                    whole_word=self.grid.GetCellValue(row, 3) == _TRUE,
                )
            )
        dictionary = Dictionary(
            id=self.id_ctrl.GetValue().strip(),
            name=self.name_ctrl.GetValue().strip(),
            description=self.description_ctrl.GetValue(),
            entries=entries,
        )
        self.store.save(dictionary)
        self._reload_list(select_id=dictionary.id)
        wx.MessageBox(f"Saved dictionary {dictionary.id!r}.", "SummaRibe")

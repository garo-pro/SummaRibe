"""Guards the screen-reader labelling of every control in the GUI.

An unlabeled control is invisible to a screen reader user, and nothing about the
visual layout shows when one slips in -- so it is checked here instead. Skipped
wherever wxPython or a display is unavailable, which is why CI runs this on the
Windows and macOS GUI jobs.
"""

from __future__ import annotations

import gc

import pytest

wx = pytest.importorskip("wx")

from summaribe.gui.accessibility import (  # noqa: E402
    ACCESSIBILITY_AVAILABLE,
    add_labelled,
    describe,
)

#: Every control class a screen reader user has to be able to identify.
_NEEDS_LABEL = (
    "wx.TextCtrl",
    "wx.Choice",
    "wx.ComboBox",
    "wx.CheckBox",
    "wx.CheckListBox",
    "wx.ListBox",
    "wx.SpinCtrl",
    "wx.SpinCtrlDouble",
    "wx.DirPickerCtrl",
    "wx.FilePickerCtrl",
    "wx.Button",
    "wx.Gauge",
)


@pytest.fixture(scope="module")
def app():
    try:
        instance = wx.App(False)
    except Exception as exc:  # pragma: no cover - headless CI without a display
        pytest.skip(f"no display available: {exc}")
    yield instance


def _accessible_name(ctrl: wx.Window) -> str | None:
    accessible = ctrl.GetAccessible()
    if accessible is None:
        return None
    status, name = accessible.GetName(0)
    return name if status == wx.ACC_OK else None


def _walk(window: wx.Window):
    for child in window.GetChildren():
        yield child
        yield from _walk(child)


def _unlabelled(window: wx.Window) -> list[str]:
    """Names of controls that a screen reader would announce with no label."""
    missing = []
    for child in _walk(window):
        class_name = f"wx.{type(child).__name__}"
        if class_name not in _NEEDS_LABEL:
            continue
        # A Button carries its own name in its label, which MSAA reads directly.
        if class_name == "wx.Button" and child.GetLabel():
            continue
        if not _accessible_name(child):
            missing.append(f"{class_name} at {child.GetPosition()}")
    return missing


@pytest.mark.skipif(
    not ACCESSIBILITY_AVAILABLE, reason="wx.Accessible is only available on Windows"
)
@pytest.mark.parametrize("tab", [0, 1, 2, 3, 4])
def test_every_control_has_an_accessible_name(app, tab):
    # conftest's autouse fixture already points the config dirs at a tmp_path.
    from summaribe.gui.main_frame import MainFrame

    frame = MainFrame(None)
    try:
        page = frame.notebook.GetPage(tab)
        missing = _unlabelled(page)
        assert not missing, (
            f"unlabelled controls on the {frame.notebook.GetPageText(tab)} tab: {missing}"
        )
    finally:
        frame.Destroy()


def test_describe_sets_the_name_msaa_reads(app):
    if not ACCESSIBILITY_AVAILABLE:
        pytest.skip("wx.Accessible is only available on Windows")
    frame = wx.Frame(None)
    try:
        ctrl = wx.TextCtrl(frame, value="the user's text")
        describe(ctrl, "Source URL", "A URL or a file path.")
        assert _accessible_name(ctrl) == "Source URL"
        status, description = ctrl.GetAccessible().GetDescription(0)
        assert (status, description) == (wx.ACC_OK, "A URL or a file path.")
        # The control's contents must not leak into its name: wxWidgets' own default
        # would have answered MSAA with GetLabel(), which for a TextCtrl is the text.
        assert _accessible_name(ctrl) != ctrl.GetValue()
    finally:
        frame.Destroy()


def test_add_labelled_builds_the_static_text_before_the_control(app):
    """Z-order is the fallback association on platforms without wx.Accessible, and it
    only works when the label is created first."""
    frame = wx.Frame(None)
    try:
        panel = wx.Panel(frame)
        sizer = wx.FlexGridSizer(cols=2, gap=(6, 6))
        ctrl = add_labelled(sizer, panel, "Audio format", wx.TextCtrl)
        children = list(panel.GetChildren())
        assert isinstance(children[0], wx.StaticText)
        assert children[0].GetLabel() == "Audio format"
        assert children[1] is ctrl
    finally:
        frame.Destroy()


def test_describe_strips_mnemonics_from_the_announced_name(app):
    if not ACCESSIBILITY_AVAILABLE:
        pytest.skip("wx.Accessible is only available on Windows")
    frame = wx.Frame(None)
    try:
        button = wx.Button(frame, label="&Run")
        describe(button, "&Run")
        assert _accessible_name(button) == "Run"
    finally:
        frame.Destroy()


def test_composite_controls_keep_their_name_after_garbage_collection(app):
    """The internal text field of a picker or spin control is the window MSAA asks,
    and its accessible is only kept alive by a Python reference -- drop that and the
    name silently reverts to nothing."""
    if not ACCESSIBILITY_AVAILABLE:
        pytest.skip("wx.Accessible is only available on Windows")
    frame = wx.Frame(None)
    try:
        panel = wx.Panel(frame)
        picker = wx.DirPickerCtrl(panel)
        spin = wx.SpinCtrlDouble(panel, min=1, max=9)
        describe(picker, "Working directory")
        describe(spin, "Timeout")
        gc.collect()
        assert _accessible_name(picker.GetChildren()[0]) == "Working directory"
        assert _accessible_name(spin.GetChildren()[0]) == "Timeout"
    finally:
        frame.Destroy()


def test_describe_leaves_a_containers_own_controls_alone(app):
    """`describe` on a notebook or scrolled window must name only the container: its
    children are real controls that already carry their own names."""
    if not ACCESSIBILITY_AVAILABLE:
        pytest.skip("wx.Accessible is only available on Windows")
    frame = wx.Frame(None)
    try:
        notebook = wx.Notebook(frame)
        page = wx.TextCtrl(notebook)
        describe(page, "Summary")
        notebook.AddPage(page, "Summary")
        describe(notebook, "Results")
        assert _accessible_name(notebook) == "Results"
        assert _accessible_name(page) == "Summary"
    finally:
        frame.Destroy()

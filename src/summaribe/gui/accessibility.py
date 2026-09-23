"""Screen-reader labelling helpers.

Why this module exists at all: wxWidgets does *not* give its controls a usable
accessible name on its own. On Windows, ``wxWindowAccessible::GetName`` answers
MSAA's ``get_accName`` from ``wxWindow::GetLabel()``, and ``wxWindowMSW::SetLabel``
is a plain ``SetWindowText`` -- so for a ``wx.TextCtrl`` the "label" is the text the
user typed, and for a ``wx.Choice`` or ``wx.SpinCtrl`` there is nothing at all.
``SetName()`` reads like the obvious fix but never reaches MSAA.

Verified against NVDA (wxPython 4.3.1 / wxWidgets 3.3.3, Windows 11), only two
things actually get announced:

* a ``wx.Accessible`` attached with ``SetAccessible()`` -- NVDA read back both the
  name and the description we supplied, for ``wx.TextCtrl``, ``wx.Choice`` and an
  otherwise label-less ``wx.CheckBox``;
* a ``wx.StaticText`` created *before* the control it labels, which Win32 picks up
  because oleacc falls back to the preceding static in Z-order.

``SetName()`` and ``SetHelpText()`` on their own produced a bare "edit" both times.

So we do both. `describe` attaches the accessible, which is what carries the name on
Windows; `add_labelled` additionally constructs the ``wx.StaticText`` before the
control, which is what carries it on GTK/macOS and keeps the visual label and the
tab order in the same order.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import wx

#: ``wx.Accessible`` only works on Windows: macOS builds export the class but its
#: constructor raises ``NotImplementedError``. Everywhere else `describe` relies on
#: the static-text-before-control ordering that `add_labelled` guarantees.
ACCESSIBILITY_AVAILABLE = wx.Platform == "__WXMSW__" and hasattr(wx, "Accessible")


if ACCESSIBILITY_AVAILABLE:

    class _ControlAccessible(wx.Accessible):  # pragma: no cover - needs a display
        """Answers MSAA with a name we chose, instead of the control's contents."""

        def __init__(self, name: str, description: str | None = None) -> None:
            super().__init__()
            self._name = name
            self._description = description

        def GetName(self, childId: int) -> tuple[int, str]:
            # Child ids address the parts of a composite control (a spin button's
            # arrows, say); only the control itself gets our name.
            if childId:
                return (wx.ACC_NOT_IMPLEMENTED, "")
            return (wx.ACC_OK, self._name)

        def GetDescription(self, childId: int) -> tuple[int, str]:
            if childId or not self._description:
                return (wx.ACC_NOT_IMPLEMENTED, "")
            return (wx.ACC_OK, self._description)


#: The window types a composite control builds itself out of -- a picker's text field
#: and browse button, a spin control's editor and arrows. These are the only children
#: `describe` renames.
_COMPOSITE_PARTS = (wx.TextCtrl, wx.Button, wx.SpinButton)

#: Containers hold controls that are nothing to do with them, and a notebook page can
#: itself be a ``wx.TextCtrl`` -- indistinguishable from a picker's internal field by
#: type alone. So the wrapper decides: `describe` never renames a container's children.
_CONTAINERS = (
    wx.Notebook,
    wx.Panel,
    wx.ScrolledWindow,
    wx.SplitterWindow,
    wx.TopLevelWindow,
)


def _strip_mnemonics(label: str) -> str:
    return label.replace("&&", "\x00").replace("&", "").replace("\x00", "&")


def describe(ctrl: wx.Window, name: str, description: str | None = None) -> None:
    """Give `ctrl` an accessible name (and optional description) for screen readers.

    `name` may carry an ``&`` mnemonic; it is stripped before being announced.
    The description is also set as a tooltip, which both sighted users and NVDA get.
    """
    name = _strip_mnemonics(name)
    if description:
        ctrl.SetToolTip(description)
    if not ACCESSIBILITY_AVAILABLE:
        return
    # Both the accessible and the window proxy have to stay referenced from Python.
    # ``SetAccessible`` does not keep the Python half of the subclass alive by itself:
    # once the proxy for a composite's child window is collected, ``GetAccessible``
    # starts handing back a plain ``wx.Accessible`` again and the name is gone. Parking
    # them on the control ties both lifetimes to the control's own.
    refs: list[object] = []
    accessible = _ControlAccessible(name, description)
    refs.append(accessible)
    ctrl.SetAccessible(accessible)

    # A composite control -- a picker, a spin control -- puts the window that actually
    # takes focus one level down, and MSAA asks *that* window for its name, so an
    # accessible on the wrapper alone is never seen. Only those internals are renamed:
    # a container's children are controls in their own right, and `describe` on a
    # notebook or a scrolled window must not overwrite the names they already carry.
    children = [] if isinstance(ctrl, _CONTAINERS) else ctrl.GetChildren()
    for child in children:
        if not isinstance(child, _COMPOSITE_PARTS):
            continue
        child_name = f"Browse for {name}" if isinstance(child, wx.Button) else name
        child_accessible = _ControlAccessible(child_name, description)
        refs.append((child, child_accessible))
        child.SetAccessible(child_accessible)

    ctrl._summaribe_accessibles = refs


def add_labelled(
    sizer: wx.Sizer,
    parent: wx.Window,
    label: str,
    factory: Callable[[wx.Window], wx.Window],
    description: str | None = None,
    *,
    proportion: int = 1,
) -> wx.Window:
    """Add a ``label`` / control pair to a two-column `sizer` and return the control.

    Takes a factory rather than a ready-made control so the ``wx.StaticText`` is
    constructed *first*: that ordering is what platforms without ``wx.Accessible``
    use to associate the label with the control.
    """
    static = wx.StaticText(parent, label=label)
    ctrl = factory(parent)
    describe(ctrl, label, description)
    sizer.Add(static, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(ctrl, proportion, wx.EXPAND)
    return ctrl


def add_stacked(
    sizer: wx.Sizer,
    parent: wx.Window,
    label: str,
    factory: Callable[[wx.Window], wx.Window],
    description: str | None = None,
    *,
    proportion: int = 0,
    flags: int = wx.EXPAND | wx.ALL,
    border: int = 8,
) -> wx.Window:
    """`add_labelled` for a vertical sizer: label on its own line above the control."""
    static = wx.StaticText(parent, label=label)
    ctrl = factory(parent)
    describe(ctrl, label, description)
    sizer.Add(static, 0, wx.LEFT | wx.TOP, border)
    sizer.Add(ctrl, proportion, flags, border)
    return ctrl


def announce(window: wx.Window, message: str) -> None:
    """Best-effort "something changed" notification to a screen reader.

    MSAA has no live-region concept, so this renames `window` and fires a name-change
    event. Screen readers are free to ignore that for an unfocused control, which is
    why callers should treat it as a supplement to -- never a replacement for -- a
    change the user can reach on their own, such as text appended to the log or a
    focus move.
    """
    if not ACCESSIBILITY_AVAILABLE:  # pragma: no cover - needs a display
        return
    accessible = _ControlAccessible(message)
    # Held for the same reason as in `describe`, and replacing the list rather than
    # appending keeps a long run from accumulating one accessible per message.
    window._summaribe_accessibles = [accessible]
    window.SetAccessible(accessible)
    wx.Accessible.NotifyEvent(wx.ACC_EVENT_OBJECT_NAMECHANGE, window, wx.OBJID_CLIENT, wx.ACC_SELF)


def uses_high_contrast() -> bool:
    """True when Windows' High Contrast mode is on.

    An app that hardcodes its own colours has to stand down in that mode, or it
    silently overrides the exact colour scheme the user chose for legibility.
    """
    # ``sys.platform`` rather than ``wx.Platform`` so mypy on other platforms treats
    # the ``ctypes.windll`` access below as unreachable instead of an error.
    if sys.platform != "win32":
        return False
    import ctypes

    class _HighContrast(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("dwFlags", ctypes.c_uint),
            ("lpszDefaultScheme", ctypes.c_wchar_p),
        ]

    info = _HighContrast()
    info.cbSize = ctypes.sizeof(_HighContrast)
    spi_gethighcontrast = 0x0042
    hcf_highcontraston = 0x00000001
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            spi_gethighcontrast, info.cbSize, ctypes.byref(info), 0
        )
    except (AttributeError, OSError):  # pragma: no cover - non-Windows or locked down
        return False
    return bool(ok) and bool(info.dwFlags & hcf_highcontraston)

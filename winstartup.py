"""winstartup.py - start the program when the user logs in to Windows (Phase 6).
Uses the current user's Run key in the registry: no administrator rights, no shortcut files.
Only meaningful in the built .exe; pure functions, no database, no UI."""
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "OfficeDocumentArchive"


class StartupError(Exception):
    pass


def _own_command():
    if not getattr(sys, "frozen", False):
        return None
    return f'"{sys.executable}"'


def _winreg():
    if not sys.platform.startswith("win"):
        raise StartupError("Starting with Windows only works on Windows.")
    import winreg
    return winreg


def is_enabled(command=None, name=VALUE_NAME):
    """True when the Run entry exists and points at this program (or at `command`)."""
    command = command or _own_command()
    if command is None or not sys.platform.startswith("win"):
        return False
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as k:
            value, _ = winreg.QueryValueEx(k, name)
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return value == command


def enable(command=None, name=VALUE_NAME):
    command = command or _own_command()
    if command is None:
        raise StartupError("Starting with Windows is only available in the built program (OfficeArchive.exe).")
    winreg = _winreg()
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, command)
    except OSError as e:
        raise StartupError(f"Windows would not save the setting: {e}")


def disable(name=VALUE_NAME):
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
    except FileNotFoundError:
        pass
    except OSError as e:
        raise StartupError(f"Windows would not remove the setting: {e}")

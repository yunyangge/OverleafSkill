"""OS-backed website sessions: Windows DPAPI or macOS native Keychain."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import sys

SERVICE = "OverleafSkill.www.overleaf.com"


def validate_profile(profile):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", profile):
        raise ValueError("Session profile must contain 1-64 letters, digits, underscores or hyphens")
    return profile


def state_dir():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "OverleafSkill"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/OverleafSkill"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "overleaf-skill"


def protect(data, decrypt=False):
    if sys.platform != "win32":
        raise RuntimeError("DPAPI is Windows-only")
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    operation = library.CryptUnprotectData if decrypt else library.CryptProtectData
    operation.restype = wintypes.BOOL
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("Windows session encryption failed")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def keychain():
    # Select the native backend explicitly; never fall back to a plaintext backend.
    from keyring.backends.macOS import Keyring
    return Keyring()


def save_cookie(value, profile="default"):
    validate_profile(profile)
    if not value or "\r" in value or "\n" in value:
        raise ValueError("Invalid cookie header")
    if sys.platform == "win32":
        folder = state_dir()
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / (profile + ".dpapi")
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(protect(value.encode()))
        os.replace(temporary, destination)
    elif sys.platform == "darwin":
        keychain().set_password(SERVICE, profile, value)
    else:
        raise RuntimeError("Website credentials are supported on Windows and macOS only")


def load_cookie(profile="default"):
    validate_profile(profile)
    if sys.platform == "win32":
        p = state_dir() / (profile + ".dpapi")
        value = protect(p.read_bytes(), decrypt=True).decode() if p.exists() else None
    elif sys.platform == "darwin":
        value = keychain().get_password(SERVICE, profile)
    else:
        raise RuntimeError("Website credentials are supported on Windows and macOS only")
    if not value:
        raise RuntimeError("LOGIN_REQUIRED: run manage.py login locally; never send cookies in chat")
    return value


def delete_cookie(profile="default"):
    validate_profile(profile)
    if sys.platform == "win32":
        (state_dir() / (profile + ".dpapi")).unlink(missing_ok=True)
    elif sys.platform == "darwin":
        backend = keychain()
        if backend.get_password(SERVICE, profile) is not None:
            backend.delete_password(SERVICE, profile)
    else:
        raise RuntimeError("Unsupported credential platform")

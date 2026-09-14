"""Dependency-free Windows mute for the frozen self-test child process.

The normal player keeps its existing audio path.  The self-test uses this
small Core Audio COM wrapper before creating the graphical application so its
own session is muted while decoding, device writes and timing remain active.
"""

import ctypes
import os
import uuid


class _GUID(ctypes.Structure):
    _fields_ = (
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    )


HRESULT = ctypes.c_long
DWORD = ctypes.c_uint32
BOOL = ctypes.c_int
ULONG = ctypes.c_uint32
CLSCTX_INPROC_SERVER = 0x1
CLSCTX_ALL = 0x17
COINIT_MULTITHREADED = 0x0
S_OK = 0
S_FALSE = 1

CLSID_MM_DEVICE_ENUMERATOR = "BCDE0395-E52F-467C-8E3D-C4579291692E"
IID_MM_DEVICE_ENUMERATOR = "A95664D2-9614-4F35-A746-DE8DB63617E6"
IID_AUDIO_SESSION_MANAGER2 = "77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"


def _guid(value):
    return _GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def _failed(hr):
    return ctypes.c_ulong(hr).value & 0x80000000 != 0


def _check(hr, operation):
    if _failed(hr):
        raise RuntimeError(f"{operation} failed (HRESULT 0x{ctypes.c_ulong(hr).value:08x})")


def _method(pointer, index, result, *arguments):
    """Return a typed callable for a COM vtable slot."""
    if not pointer:
        raise RuntimeError("Audio COM returned a null interface")
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    address = vtable[index]
    if not address:
        raise RuntimeError(f"Audio COM method {index} is unavailable")
    return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *arguments)(address)


class ProcessMute:
    """Keep this process's default render session muted until ``close``."""

    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("The self-test mute requires Windows Core Audio")
        self._enumerator = None
        self._device = None
        self._manager = None
        self._volume = None
        self._com_initialized = False
        try:
            ole32 = ctypes.WinDLL("ole32", use_last_error=True)
            self._ole32 = ole32
            ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, DWORD]
            ole32.CoInitializeEx.restype = HRESULT
            ole32.CoUninitialize.argtypes = []
            ole32.CoUninitialize.restype = None
            result = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
            if result not in (S_OK, S_FALSE):
                _check(result, "CoInitializeEx")
            self._com_initialized = True

            ole32.CoCreateInstance.argtypes = [
                ctypes.POINTER(_GUID), ctypes.c_void_p, DWORD,
                ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p),
            ]
            ole32.CoCreateInstance.restype = HRESULT
            enumerator = ctypes.c_void_p()
            _check(ole32.CoCreateInstance(
                ctypes.byref(_guid(CLSID_MM_DEVICE_ENUMERATOR)), None,
                CLSCTX_INPROC_SERVER,
                ctypes.byref(_guid(IID_MM_DEVICE_ENUMERATOR)),
                ctypes.byref(enumerator),
            ), "CoCreateInstance(MMDeviceEnumerator)")
            self._enumerator = enumerator

            device = ctypes.c_void_p()
            get_default = _method(enumerator, 4, HRESULT, DWORD, DWORD,
                                   ctypes.POINTER(ctypes.c_void_p))
            _check(get_default(enumerator, 0, 1, ctypes.byref(device)),
                   "GetDefaultAudioEndpoint")
            self._device = device

            manager = ctypes.c_void_p()
            activate = _method(device, 3, HRESULT, ctypes.POINTER(_GUID),
                               DWORD, ctypes.c_void_p,
                               ctypes.POINTER(ctypes.c_void_p))
            _check(activate(device, ctypes.byref(_guid(IID_AUDIO_SESSION_MANAGER2)),
                            CLSCTX_ALL, None, ctypes.byref(manager)),
                   "IMMDevice.Activate(IAudioSessionManager2)")
            self._manager = manager

            volume = ctypes.c_void_p()
            get_simple = _method(manager, 4, HRESULT, ctypes.c_void_p, DWORD,
                                 ctypes.POINTER(ctypes.c_void_p))
            # NULL session GUID plus FALSE cross-process selects this process's
            # default session, matching the known working pycaw call.
            _check(get_simple(manager, None, 0, ctypes.byref(volume)),
                   "GetSimpleAudioVolume")
            self._volume = volume

            set_mute = _method(volume, 5, HRESULT, BOOL,
                               ctypes.POINTER(_GUID))
            _check(set_mute(volume, 1, None), "SetMute")
            if not self.is_muted():
                raise RuntimeError("GetMute did not confirm the self-test session is muted")
        except Exception:
            self.close()
            raise

    def is_muted(self):
        """Read and return the current mute state from this COM session."""
        muted = BOOL()
        get_mute = _method(self._volume, 6, HRESULT, ctypes.POINTER(BOOL))
        _check(get_mute(self._volume, ctypes.byref(muted)), "GetMute")
        return bool(muted.value)

    def close(self):
        if getattr(self, "_volume", None):
            _method(self._volume, 2, ULONG)(self._volume)
            self._volume = None
        if getattr(self, "_manager", None):
            _method(self._manager, 2, ULONG)(self._manager)
            self._manager = None
        if getattr(self, "_device", None):
            _method(self._device, 2, ULONG)(self._device)
            self._device = None
        if getattr(self, "_enumerator", None):
            _method(self._enumerator, 2, ULONG)(self._enumerator)
            self._enumerator = None
        if getattr(self, "_com_initialized", False):
            self._ole32.CoUninitialize()
            self._com_initialized = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def mute_current_process():
    """Mute and return a guard that must live for the playback run."""
    return ProcessMute()

"""Replaceable libopenmpt C ABI renderer; no campaign state or gameplay RNG."""
import ctypes as c
import os
from pathlib import Path
import platform
import sys
from ..core import GameError,integer
from .module_music import ModuleSong


def default_library():
    configured=os.environ.get('OPENREUNION_MODULE_LIBRARY')
    if configured:return Path(configured)
    name='libopenmpt.dll' if os.name=='nt' else 'libopenmpt.dylib' if platform.system()=='Darwin' else 'libopenmpt.so'
    if getattr(sys,'frozen',False):return Path(sys._MEIPASS)/'local/native'/name
    return Path(__file__).resolve().parents[3]/'local/native'/name


class ModuleRenderer:
    def __init__(self,song,rate=48000,*,repeat=True,library=None):
        if not isinstance(song,ModuleSong):raise GameError('Expected validated original module music.')
        integer(rate,'Module sample rate',minimum=8000,maximum=192000)
        if type(repeat) is not bool:raise GameError('Invalid module repeat setting.')
        self.rate=rate;self.frames=0;self.ended=False;self._module=None
        path=Path(library) if library else default_library()
        try:self.lib=c.CDLL(str(path.resolve()))
        except OSError as exc:raise GameError('Module audio library is unavailable. Install the local libopenmpt runtime.') from exc
        signatures={
            'openmpt_module_create_from_memory2':([c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,c.POINTER(c.c_int),c.POINTER(c.c_void_p),c.c_void_p],c.c_void_p),
            'openmpt_free_string':([c.c_void_p],None),
            'openmpt_module_destroy':([c.c_void_p],None),
            'openmpt_module_set_repeat_count':([c.c_void_p,c.c_int32],c.c_int),
            'openmpt_module_ctl_set_integer':([c.c_void_p,c.c_char_p,c.c_int64],c.c_int),
            'openmpt_module_ctl_set_boolean':([c.c_void_p,c.c_char_p,c.c_int],c.c_int),
            'openmpt_module_ctl_set_text':([c.c_void_p,c.c_char_p,c.c_char_p],c.c_int),
            'openmpt_module_read_interleaved_stereo':([c.c_void_p,c.c_int32,c.c_size_t,c.POINTER(c.c_int16)],c.c_size_t),
            'openmpt_module_get_duration_seconds':([c.c_void_p],c.c_double),
            'openmpt_module_get_current_order':([c.c_void_p],c.c_int32),
            'openmpt_module_get_current_row':([c.c_void_p],c.c_int32),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.lib,name);fn.argtypes=args;fn.restype=result
        error=c.c_int();message=c.c_void_p();data=c.create_string_buffer(song.data)
        self._module=self.lib.openmpt_module_create_from_memory2(data,len(song.data),
            c.cast(self.lib.openmpt_log_func_silent,c.c_void_p),None,
            c.cast(self.lib.openmpt_error_func_store,c.c_void_p),None,c.byref(error),c.byref(message),None)
        try:
            if not self._module:raise GameError('Module music could not be decoded.')
            self._check(self.lib.openmpt_module_set_repeat_count(self._module,-1 if repeat else 0))
            self._check(self.lib.openmpt_module_ctl_set_integer(self._module,b'dither',0))
            self._check(self.lib.openmpt_module_ctl_set_boolean(self._module,b'render.resampler.emulate_amiga',0))
            self._check(self.lib.openmpt_module_ctl_set_text(self._module,b'play.at_end',b'stop'))
        except BaseException:self.close();raise
        finally:
            if message.value:self.lib.openmpt_free_string(message)

    @staticmethod
    def _check(value):
        if not value:raise GameError('Module audio configuration failed.')

    @property
    def duration(self):
        if self._module is None:raise GameError('Module renderer is closed.')
        return self.lib.openmpt_module_get_duration_seconds(self._module)

    @property
    def position(self):
        if self._module is None:raise GameError('Module renderer is closed.')
        return (self.lib.openmpt_module_get_current_order(self._module),self.lib.openmpt_module_get_current_row(self._module))

    def render(self,frames):
        integer(frames,'Module render frames',maximum=192000)
        if self._module is None:raise GameError('Module renderer is closed.')
        buffer=(c.c_int16*(frames*2))()
        count=self.lib.openmpt_module_read_interleaved_stereo(self._module,self.rate,frames,buffer)
        if count>frames:raise GameError('Module renderer returned too many samples.')
        self.ended=self.ended or count<frames;self.frames+=frames
        return bytes(buffer)

    def seek(self,frames,cancel=lambda:False):
        integer(frames,'Module sample position',minimum=self.frames,maximum=2**53-1)
        while self.frames<frames:
            if cancel():return False
            self.render(min(16384,frames-self.frames))
        return True

    def close(self):
        if self._module:self.lib.openmpt_module_destroy(self._module);self._module=None

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

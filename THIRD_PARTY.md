# Third-party components

Open Reunion's original code is MIT licensed. Separately licensed components
retain their own licenses and notices.

## Nuked OPL3

The optional FM synthesizer uses [Nuked OPL3](https://github.com/nukeykt/Nuked-OPL3),
copyright Nuke.YKT, under LGPL-2.1-or-later. Its unmodified C source, header and
full license are in `third_party/nuked_opl3`. `UPSTREAM.json` records commit
`765ec962e473aeb767e4cba74ffdc8f588ffbfe8` and each downloaded file's hash.

Open Reunion's MIT-licensed `native/opl_bridge.c` provides an opaque C ABI.
`tools/build_audio.py` builds the source into a separate shared library under
`local/native`. The Python adapter dynamically loads that library; set
`OPENREUNION_OPL_LIBRARY` to use a replacement compatible with ABI version 1.
The complete source and build command are provided for rebuilding it.

The Windows importer package includes this replaceable DLL, these notices,
the full license, matching source and build instructions. The historical wheel
does not contain the current audio-enabled client.

The local build toolchain is the MIT-licensed Zig 0.16.0 distribution from
[the ziglang package](https://pypi.org/project/ziglang/0.16.0/). It is a build
dependency in `local/build-tools`, not part of the game runtime.

## libopenmpt module music

The original sample-based music uses the separately replaceable
[libopenmpt](https://lib.openmpt.org/libopenmpt/) 0.8.9 decoder (BSD-3-Clause).
`third_party/libopenmpt/UPSTREAM.json` records the pinned official binary/source
archive URLs and SHA-256 hashes, plus each installed DLL/header/license hash.
The full notices are retained in that directory, including the codec
dependencies' notices. The mpg123 dependency is LGPL-2.1; its matching source,
along with the complete library and other dependencies, is included in
`source-0.8.9-msvc.zip` in the same directory. The source archive contains the
VS2022 Windows 10 solution `build/vs2022win10/libopenmpt.sln` and dependency
projects. No upstream source or DLL was modified.

`python tools/install_module_audio.py` installs the pinned Windows x64 DLLs
under `local/native`, using cached archives where present. The runtime loads
the C ABI dynamically. `OPENREUNION_MODULE_LIBRARY` selects a replacement
library; accompanying dependency DLLs must be available beside it. The package
builder includes DLLs, matching source and notices, and asks PyInstaller to
collect their runtime dependencies. A frozen module-audio verification is still
required for each new runtime package.

## Windows test runtime

The test package bundles Python 3.14.2 and Tcl/Tk through PyInstaller 6.19.0.
Their notices are in `licenses/` in the package. Python's license file also
contains notices for its bundled runtime components. Additional OpenSSL,
Tcl and zlib-ng notices are retained in `third_party/runtime-notices` and copied
to `licenses/`; `SOURCES.json` records their upstream URLs and hashes.

PyInstaller's license includes an exception for bundled applications. Its full
license and the hooks package's license are included. The Microsoft runtime
files supplied with Python retain the conditions recorded in Python's license.

Original game graphics, text, music and other converted assets are separate
from Open Reunion's MIT-licensed implementation. They retain their original
ownership and are not included in this repository or the public package builder.

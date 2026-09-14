"""Build the pinned, replaceable Nuked OPL3 shared library locally."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler',type=Path,help='C compiler, or the zig executable')
    args=p.parse_args();vendor=ROOT/'third_party/nuked_opl3'
    manifest=json.loads((vendor/'UPSTREAM.json').read_text())
    for name,digest in manifest['files'].items():
        if hashlib.sha256((vendor/name).read_bytes()).hexdigest()!=digest:
            p.error(f'Upstream source hash changed: {name}; update provenance before rebuilding.')
    compiler=args.compiler
    if not compiler:
        local=ROOT/'local/build-tools/ziglang'/('zig.exe' if os.name=='nt' else 'zig')
        compiler=local if local.is_file() else shutil.which('cc') or shutil.which('clang')
    if not compiler:p.error('Install a C compiler or local ziglang, then use --compiler.')
    compiler=Path(compiler).resolve()
    command=[str(compiler)]+(['cc'] if compiler.stem=='zig' else [])
    extension='.dll' if os.name=='nt' else '.dylib' if platform.system()=='Darwin' else '.so'
    output=ROOT/'local/native'/('openreunion_opl'+extension);output.parent.mkdir(parents=True,exist_ok=True)
    command+=['-O2','-shared','-I',str(vendor),str(ROOT/'native/opl_bridge.c'),str(vendor/'opl3.c'),'-o',str(output)]
    if os.name!='nt':command+=['-fPIC']
    env=os.environ.copy();env['ZIG_GLOBAL_CACHE_DIR']=str(ROOT/'local/build-cache/global')
    env['ZIG_LOCAL_CACHE_DIR']=str(ROOT/'local/build-cache/local')
    subprocess.run(command,cwd=ROOT,env=env,check=True)
    report={'upstream_commit':manifest['commit'],'compiler':str(compiler),'command':command,
            'library':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
    (output.parent/'audio-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

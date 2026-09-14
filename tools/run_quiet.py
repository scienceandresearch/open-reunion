"""Start a project test with its Windows audio session muted before playback.

This changes OS output only: decoding, device writes, playback completion,
game settings and campaign state remain intact. It does not mute other PIDs.
"""
import argparse
import os
from pathlib import Path
import runpy
import sys

PROJECT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Verify session mute without launching a test')
    parser.add_argument('script',nargs='?',type=Path)
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if not args.check:
        if args.script is None:parser.error('Provide a test script under opensource/tools')
        script=args.script.resolve()
        if not script.is_relative_to(PROJECT/'tools') or not script.is_file() or script.suffix!='.py':
            parser.error('Choose an existing Python script under opensource/tools')
    sys.path.insert(0,str(PROJECT/'src'))
    from openreunion.testing_audio import mute_current_process
    # Share the dependency-free pre-playback guard with frozen self-tests.
    # Its default session is process-local; retain it for the whole run.
    with mute_current_process() as volume:
        assert volume.is_muted()
        print(f'Windows test audio muted before playback (PID {os.getpid()}); audio engine remains enabled.',flush=True)
        if args.check:return
        sys.path.insert(0,str(script.parent))
        sys.argv=[str(script),*args.arguments]
        runpy.run_path(str(script),run_name='__main__')


if __name__=='__main__':main()

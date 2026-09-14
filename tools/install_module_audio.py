"""Install pinned official Windows x64 module decoder and matching source locally."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.8.9'
ARCHIVES={
    'dev':('https://lib.openmpt.org/files/libopenmpt/dev/libopenmpt-0.8.9%2Brelease.dev.windows.vs2022.zip',
           'local/downloads/libopenmpt-0.8.9-windows.zip','a23e375e576e3a6997ffeeb6cf34488e9020e2a5d8226856b02628b6a87c5e8e'),
    'source':('https://lib.openmpt.org/files/libopenmpt/src/libopenmpt-0.8.9%2Brelease.msvc.zip',
              'third_party/libopenmpt/source-0.8.9-msvc.zip','8d3b3c14b92dd1fcbb31b2bf28ed917c1d3b529b0d9380562d5bdb6256d32bea')}


def main():
    for url,relative,digest in ARCHIVES.values():
        path=ROOT/relative
        if path.exists():data=path.read_bytes()
        else:
            with urllib.request.urlopen(url,timeout=30) as stream:data=stream.read(100*1024*1024+1)
        if len(data)>100*1024*1024 or hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Module runtime archive does not match the pinned official release')
        if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    rows=[]
    with zipfile.ZipFile(ROOT/ARCHIVES['dev'][1]) as archive:
        mapping={'LICENSE.txt':'third_party/libopenmpt/LICENSE.txt',
                 'inc/libopenmpt/libopenmpt.h':'third_party/libopenmpt/libopenmpt.h'}
        for name in ('libopenmpt','openmpt-mpg123','openmpt-ogg','openmpt-vorbis','openmpt-zlib'):
            mapping[f'bin/amd64/{name}.dll']=f'local/native/{name}.dll'
        for member in archive.namelist():
            if member.startswith('Licenses/') and not member.endswith('/'):
                if Path(member).name!=member[len('Licenses/'):]:raise ValueError('Unexpected nested license entry')
                mapping[member]='third_party/libopenmpt/'+member
        for member,relative in mapping.items():
            path=ROOT/relative;data=archive.read(member)
            if path.exists() and path.read_bytes()!=data:raise ValueError(f'Existing file differs: {relative}')
            if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            rows.append({'member':member,'path':relative,'sha256':hashlib.sha256(data).hexdigest()})
    record={'version':VERSION,'archives':{key:{'url':url,'path':relative,'sha256':digest} for key,(url,relative,digest) in ARCHIVES.items()},'files':rows}
    (ROOT/'third_party/libopenmpt/UPSTREAM.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Installed pinned libopenmpt',VERSION,'and matching source under opensource.')


if __name__=='__main__':main()

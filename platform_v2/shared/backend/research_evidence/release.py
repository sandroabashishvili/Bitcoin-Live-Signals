"""Stdlib-only source snapshot builder and pinned Python launcher.

Run this file directly, before importing any platform_v2 module. A release retains
Python source while __file__ paths continue resolving the existing runtime/data.
No deployment, process start, or service install occurs when building a bundle.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import runpy
import sys


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()


def build(root, destination):
    root=Path(root).resolve()
    files={str(p.relative_to(root)):p.read_text() for p in sorted((root/'platform_v2').rglob('*.py'))
           if not {'runtime','__pycache__','public_site'} & set(p.relative_to(root).parts)}
    for name,source in files.items():
        compile(source,str(root/name),'exec')
        if (root/name).read_text()!=source:
            raise RuntimeError('source changed during release capture')
    payload={'format':1,'project_root':str(root),'files':files}
    data=encode(payload)
    digest=hashlib.sha256(data).hexdigest()
    target=Path(destination)/digest
    target.mkdir(parents=True,exist_ok=False)
    (target/'source.json.gz').write_bytes(gzip.compress(data,mtime=0))
    (target/'run.py').write_text(Path(__file__).read_text())
    (target/'sha256.txt').write_text(digest+'\n')
    for p in target.iterdir(): p.chmod(0o444)
    target.chmod(0o555)
    return target,digest


class PinnedSource(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,payload):
        self.root=Path(payload['project_root'])
        self.files=payload['files']

    def resolve(self,name):
        base=name.replace('.','/')
        if base+'/__init__.py' in self.files: return base+'/__init__.py',True
        if base+'.py' in self.files: return base+'.py',False
        return None,False

    def find_spec(self,fullname,path=None,target=None):
        if fullname!='platform_v2' and not fullname.startswith('platform_v2.'):
            return None
        name,package=self.resolve(fullname)
        if name:
            spec=importlib.util.spec_from_loader(fullname,self,origin=str(self.root/name),is_package=package)
            spec.has_location=True
            if package: spec.submodule_search_locations=[str((self.root/name).parent)]
            return spec
        prefix=fullname.replace('.','/')+'/'
        if any(n.startswith(prefix) for n in self.files):
            spec=importlib.util.spec_from_loader(fullname,loader=None,is_package=True)
            spec.submodule_search_locations=[str(self.root/prefix)]
            return spec
        raise ModuleNotFoundError('module absent from pinned release: '+fullname)

    def create_module(self,spec): return None

    def exec_module(self,module):
        exec(self.get_code(module.__name__),module.__dict__)

    def get_filename(self,fullname):
        name,_=self.resolve(fullname)
        if name is None: raise ImportError(fullname)
        return str(self.root/name)

    def get_source(self,fullname):
        name,_=self.resolve(fullname)
        return self.files[name]

    def get_code(self,fullname):
        return compile(self.get_source(fullname),self.get_filename(fullname),'exec',dont_inherit=True)

    def is_package(self,fullname): return self.resolve(fullname)[1]


def install(source,expected_sha256):
    if any(name=='platform_v2' or name.startswith('platform_v2.') for name in sys.modules):
        raise RuntimeError('pinned launcher must run before project imports')
    data=gzip.decompress(Path(source).read_bytes())
    digest=hashlib.sha256(data).hexdigest()
    if digest!=expected_sha256: raise ValueError('release hash mismatch')
    payload=json.loads(data)
    if payload.get('format')!=1: raise ValueError('unsupported release format')
    finder=PinnedSource(payload)
    sys.meta_path.insert(0,finder)
    sys._ssh_pinned_release={'sha256':digest,'source_bundle':payload,'finder':finder}
    sys._ssh_release_launch={'runner':str(Path(__file__).resolve()),'source':str(Path(source).resolve()),'sha256':digest}
    return finder


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--release',type=Path)
    p.add_argument('--sha256')
    p.add_argument('--module')
    p.add_argument('args',nargs=argparse.REMAINDER)
    args=p.parse_args()
    if args.build:
        if not args.output: p.error('--output is required for build')
        target,digest=build(args.build,args.output)
        print(json.dumps({'release':str(target),'sha256':digest}))
        return 0
    if not args.release or not args.sha256 or not args.module:
        p.error('--release, --sha256 and --module are required')
    install(args.release,args.sha256)
    sys.argv=[args.module,*([*args.args[1:]] if args.args[:1]==['--'] else args.args)]
    runpy.run_module(args.module,run_name='__main__',alter_sys=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())

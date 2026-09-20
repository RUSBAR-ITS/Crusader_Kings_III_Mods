"""Shared CK3 localization routines. No third-party dependencies."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import os

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(os.environ.get('FAB_WORKSHOP_ROOT','E:/SteamLibrary/steamapps/workshop/content/1158310/3765282284'))
OLD = Path(os.environ.get('FAB_REFERENCE_ROOT','E:/SteamLibrary/steamapps/workshop/content/1158310/3766951310'))
ENTRY = re.compile(r'^\s*([^\s#":]+):\s*(?:\d+\s*)?"(.*)"\s*$')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def read_catalog(root, language):
    entries, files = {}, []
    for p in sorted((root/'localization').rglob(f'*_l_{language}.yml')):
        b = p.read_bytes()
        rel = p.relative_to(root).as_posix()
        files.append(dict(file=rel, sha256=hashlib.sha256(b).hexdigest()))
        for n,line in enumerate(b.decode('utf-8-sig').splitlines(),1):
            m=ENTRY.match(line)
            if m:
                k,v=m.groups()
                entries[k]=dict(key=k,text=v,file=rel,line=n)
    return entries,files


def tokens(text):
    result=[]
    i=0
    while i < len(text):
        start=i
        if text[i]=='[':
            depth=1;i+=1
            while i<len(text) and depth:
                depth += (text[i]=='[')-(text[i]==']');i+=1
            result.append((start,i,text[start:i]));continue
        m=re.match(r'\$[^$]+\$|@[^\s!]+!|#(?:!|[A-Za-z][A-Za-z0-9_;:.,-]*)',text[i:])
        if m:
            i+=len(m[0]);result.append((start,i,m[0]));continue
        i+=1
    return result


def signature(text):
    return Counter(t for _,_,t in tokens(text))


def mask(text):
    protected={}
    for n,(start,end,token) in reversed(list(enumerate(tokens(text)))):
        marker=f'ZXQ{n:04d}QXZ'
        protected[marker]=token
        text=text[:start]+marker+text[end:]
    return text.replace('\\n','\n'),protected


def unmask(text, protected):
    for marker,token in protected.items():
        if text.count(marker)!=1:
            raise ValueError(f'Protected token changed: {marker}: {text[:100]}')
        text=text.replace(marker,token)
    return text.strip().replace('\r','').replace('\n','\\n')

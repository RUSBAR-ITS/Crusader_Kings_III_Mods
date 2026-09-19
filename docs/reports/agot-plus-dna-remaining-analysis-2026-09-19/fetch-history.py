"""Fetch small public source files into report evidence, never game directories."""
from pathlib import Path
import urllib.request, json, sys, hashlib
OUT = Path(__file__).resolve().parent / 'historical'
OUT.mkdir(exist_ok=True)
def fetch(url, name):
    req = urllib.request.Request(url, headers={'User-Agent':'CK3-DNA-compatibility-research'})
    data = urllib.request.urlopen(req, timeout=45).read()
    (OUT / name).write_bytes(data)
    ledger = OUT / 'downloads.json'
    records = json.loads(ledger.read_text()) if ledger.exists() else {}
    records[name] = dict(URL=url, SHA256=hashlib.sha256(data).hexdigest(), Bytes=len(data))
    ledger.write_text(json.dumps(records, indent=2)+'\n', newline='\n')
    return data
if __name__ == '__main__':
    result = fetch(sys.argv[1], sys.argv[2])
    if '--print' in sys.argv: print(result.decode('utf-8-sig'))

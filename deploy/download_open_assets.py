"""Install redistributable default audio assets with their license notices."""
from pathlib import Path
import hashlib,os,urllib.request

root=Path(os.getenv('QINSCAPE_ASSETS','/root/autodl-tmp/qinscape/assets'));root.mkdir(parents=True,exist_ok=True)
items=[
    ('MuseScore_General.sf3','https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf3'),
    # The upstream binary mirror does not carry a sidecar notice.  Keep the
    # public GitHub mirror's exact MIT notice beside the downloaded asset.
    ('MuseScore_General_LICENSE.md','https://raw.githubusercontent.com/Tenglon/music/main/public/soundfont/MuseScore_General_LICENSE.md'),
]
for name,url in items:
    target=root/name
    if not target.exists():
        print(f'Downloading {name}');urllib.request.urlretrieve(url,target)
    digest=hashlib.sha256(target.read_bytes()).hexdigest();print(f'{digest}  {target}')
print('MuseScore General is MIT-licensed; retain the downloaded license notice when redistributing it.')

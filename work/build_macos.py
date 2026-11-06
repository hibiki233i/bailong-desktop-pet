from pathlib import Path
import sys,subprocess,shutil,json,plistlib
root=Path(__file__).resolve().parents[1]
if sys.platform!='darwin':raise SystemExit('必须在Mac上运行；本脚本不生成Windows包。')
# Install requirements-macos.txt in a clean virtual environment first.
import PyInstaller.__main__
from PIL import Image
version=(root/'VERSION.txt').read_text(encoding='utf-8').strip()
FOLDERS=['outputs/Claude桌宠素材','outputs/白龙桌宠素材']
playback=lambda v:v.get('playbackFile') or v['file'].replace('.webm','.webp')
def clips(m):
    return [m['idle']]+m.get('additionalIdleAnimations',[])+m['variants']+[v for v in m.get('workAnimations',[]) if v]+m.get('movementAnimations',[])+[m[k] for k in ('dragAnimation','landingAnimation','quotaAnimation','askAnimation') if m.get(k)]
sets=[(folder,json.loads((root/folder/'素材清单.json').read_text(encoding='utf-8'))) for folder in FOLDERS if (root/folder/'素材清单.json').is_file()]
if not sets:raise SystemExit('outputs 里没有素材。')
work=root/'.build-macos';work.mkdir(exist_ok=True)
# Finder shows this icon. Pillow cannot read WebM, so such an asset set keeps the default icon.
icon=[]
first=root/sets[0][0]/playback(sets[0][1]['idle'])
if first.suffix!='.webm':
    with Image.open(first) as source:
        frame=source.convert('RGBA');frame=frame.crop(frame.getbbox());side=max(frame.size)
        square=Image.new('RGBA',(side,side));square.paste(frame,((side-frame.width)//2,(side-frame.height)//2))
        square.resize((1024,1024),Image.Resampling.LANCZOS).save(work/'BailongPet.icns')
    icon=['--icon',str(work/'BailongPet.icns')]
PyInstaller.__main__.run(['--noconfirm','--clean','--windowed','--name','BailongPet','--osx-bundle-identifier','com.bailongpet.desktop','--distpath',str(root/'dist-macos'),'--workpath',str(work),'--specpath',str(work),*icon,'--hidden-import','autostart','--hidden-import','mac_autostart','--hidden-import','selftest','--hidden-import','pet_hub','--hidden-import','control_panel','--hidden-import','claude_limits','--hidden-import','claude_status','--hidden-import','desktop_task_sync','--hidden-import','AppKit','--hidden-import','Quartz','--hidden-import','PySide6.QtMultimedia',str(root/'app/pet.py')])
app=root/'dist-macos/BailongPet.app'
resources=app/'Contents/Resources'
for folder,m in sets:
    assets=root/folder;dest=resources/folder;dest.mkdir(parents=True,exist_ok=True)
    for v in clips(m):
        for rel in filter(None,(playback(v),(v.get('returnTransition') or {}).get('file'))):
            target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(assets/rel,target)
        v.pop('source',None)
    (dest/'素材清单.json').write_text(json.dumps(m,ensure_ascii=False),encoding='utf-8')
(resources/'app').mkdir(exist_ok=True);shutil.copytree(root/'app/sounds',resources/'app/sounds',dirs_exist_ok=True)
# WebM clips need libvpx-vp9 for alpha. Homebrew's ffmpeg depends on its own dylibs, so bundle a static one.
if any(playback(v).endswith('.webm') for _,m in sets for v in clips(m)):
    import imageio_ffmpeg
    tools=resources/'tools';tools.mkdir(exist_ok=True);ffmpeg=tools/'ffmpeg'
    shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(),ffmpeg);ffmpeg.chmod(0o755)
    subprocess.run(['codesign','--force','--sign','-',str(ffmpeg)],check=True)
    licenses=resources/'licenses';licenses.mkdir(exist_ok=True)
    (licenses/'FFmpeg.txt').write_bytes(subprocess.check_output([str(ffmpeg),'-L'],stderr=subprocess.STDOUT))
p=app/'Contents/Info.plist';data=plistlib.loads(p.read_bytes())
data.update(LSUIElement=True,CFBundleShortVersionString=version,CFBundleVersion=version,CFBundleDisplayName='AI 桌宠')
p.write_bytes(plistlib.dumps(data))
# Re-sign after resources/plist changes. Ad-hoc signing is for local testing only.
subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
print('生成了本机构架的未公证测试.app。公开发布前必须进行Mac实机验收、正式签名和公证。')

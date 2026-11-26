"""Generate the local pixel atlas and runtime tile runs from the same 16px drawings.
Run from any directory: python system/tools/build_monster_icon_atlas.py
No Roblox upload or external asset is required. Pillow is used only by the authoring tool.
"""
from pathlib import Path
import json, math
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'system/control-center/static/monster-icons'
OUT.mkdir(parents=True, exist_ok=True)
# name, silhouette, body, shade, accent; original pixel portraits, no external images.
TILES = [
 ('Toad','toad','#85b65b','#426a39','#e9ce64'),
 ('Mandragora','flower','#e7a1a9','#9a4d7c','#70bc72'),
 ('Wooden Guardian','wood','#a9784a','#5b3926','#88c66c'),
 ('Living Scarecrow','scarecrow','#ceaa68','#755034','#f5cc6d'),
 ('Wolf','wolf','#a4adb8','#4c5269','#f2cb6b'),
 ('Zombie','zombie','#85956a','#414f43','#d2bb91'),
 ('Giant Spider','spider','#775274','#3b284a','#e97482'),
 ('Skeleton Archer','skull','#e1dfc2','#888b83','#8cddbc'),
 ('Ice Vale Master','wraith','#b2e6fb','#486b9f','#d9faff'),
 ('Grizzly','bear','#a37247','#513825','#e8bb82'),
 ('Scarab','beetle','#4ea4a7','#245160','#e9c76a'),
 ('Gremlin','goblin','#91bd61','#466c3b','#f0cd66'),
 ('Stone Golem','golem','#9ba9ae','#596671','#65c9dd'),
 ('Greater Golem','golem','#ad8b72','#5d4d50','#fbb960'),
 ('Tiger','tiger','#edaa4d','#9f5c32','#fff0cc'),
 ('Ancient Treant','tree','#8b7850','#4b4533','#a6d77c'),
 ('Spore Spitter','mushroom','#d18acb','#724e94','#f1c6de'),
 ('Orc Warrior','orc','#8aa259','#4a6038','#e5c687'),
 ('Orc Archer','hood','#7e9a5d','#415d45','#e3bd75'),
 ('Orc Shaman','shaman','#849c6a','#434d58','#6ce7da'),
 ('Succubus','demon','#d78caa','#753b6b','#f6c0df'),
 ('Magical Weaver','eye','#a88fdb','#493d7f','#8df3ee'),
 ('Fire Vale Master','wraith','#f0a256','#a04d47','#ffec82'),
 ('Drake','dragon','#78a59c','#365f60','#f5d575'),
 ('Wyrm','wyrm','#b888b7','#634b87','#ffd477'),
 ('Unknown','unknown','#8f99a8','#4c596a','#ebedf3'),
]

def sprite(kind,b,s,a):
    im=Image.new('RGBA',(16,16));d=ImageDraw.Draw(im);o='#202331';white='#f4ead4';black='#242233'
    def poly(points,color): d.polygon(points,fill=color)
    def rect(x,y,X,Y,c): d.rectangle((x,y,X,Y),fill=c)
    def eye(x,y,c=a): rect(x,y,x+1,y,c);rect(x,y+1,x,y+1,black)
    def face():
        poly([(3,4),(5,2),(10,2),(13,5),(13,11),(10,14),(5,14),(2,11),(2,6)],o)
        poly([(4,4),(6,3),(10,3),(12,5),(12,10),(9,13),(6,13),(3,10),(3,6)],b)
        poly([(10,4),(12,5),(12,10),(9,13),(7,13),(10,10)],s)
        eye(5,7);eye(10,7);rect(6,11,9,11,s)
    if kind=='toad':
        poly([(1,7),(2,3),(5,2),(7,4),(9,4),(11,2),(14,3),(15,7),(14,12),(11,14),(4,14),(1,11)],o)
        poly([(2,7),(3,4),(5,3),(7,6),(9,6),(11,3),(13,4),(14,7),(13,11),(10,13),(5,13),(2,10)],b)
        eye(3,5);eye(11,5);rect(4,10,11,10,s);rect(6,11,9,11,a)
    elif kind=='flower':
        for x,y in [(5,1),(9,1),(2,4),(12,4),(2,8),(12,8),(5,12),(9,12)]:
            d.ellipse((x-2,y-1,x+2,y+3),fill=o);d.ellipse((x-1,y,x+1,y+2),fill=b)
        face();rect(5,5,10,6,a);rect(4,4,5,5,a);rect(11,4,12,5,a)
    elif kind in ('wolf','bear','tiger','dragon','wyrm'):
        if kind=='bear':
            for x in (2,11): rect(x,1,x+3,5,o);rect(x+1,2,x+2,4,s)
        else:
            poly([(2,8),(1,1),(6,4),(10,4),(14,0),(14,9)],o)
            poly([(3,5),(2,2),(5,5),(11,5),(13,2),(13,6)],s)
        face();poly([(5,9),(7,8),(9,8),(11,10),(10,13),(5,13),(4,11)],white if kind in ('wolf','tiger') else s)
        rect(7,9,8,10,black);rect(6,12,9,12,black)
        if kind=='tiger':
            for x,y in [(4,5),(10,5),(3,9),(11,9),(7,3)]:rect(x,y,x+1,y+1,black)
        if kind in ('dragon','wyrm'):
            poly([(3,5),(2,0),(6,4),(10,4),(13,0),(12,6)],a);rect(5,12,5,13,white);rect(10,12,10,13,white)
            if kind=='wyrm': poly([(6,4),(8,0),(10,4)],a);rect(7,5,8,6,a)
    elif kind in ('wood','tree','golem'):
        poly([(2,5),(4,2),(11,2),(14,5),(14,11),(11,14),(4,14),(1,11)],o)
        poly([(3,5),(5,3),(10,3),(13,6),(13,10),(10,13),(5,13),(2,10)],b)
        rect(3,6,12,8,s);eye(4,7);eye(10,7);rect(6,11,9,12,s)
        if kind in ('wood','tree'):
            for x,y in [(4,3),(10,3),(3,10),(11,10)]:rect(x,y,x,y+3,s)
            if kind=='tree':poly([(1,3),(0,0),(3,2),(5,0),(6,4),(10,3),(12,0),(15,2),(14,5)],a)
        else:
            poly([(7,3),(9,5),(7,6),(9,9),(7,10)],s);rect(7,4,7,5,a)
    elif kind=='scarecrow':
        face();rect(2,4,13,5,o);rect(4,1,11,3,s);rect(3,3,12,4,b);rect(4,8,5,9,black);rect(10,8,11,9,black);rect(5,11,10,11,black)
        for x in (5,7,9):rect(x,10,x,12,a)
    elif kind in ('zombie','skull'):
        face();rect(4,6,6,8,black);rect(9,6,11,8,black);rect(5,7,5,7,a);rect(10,7,10,7,a);rect(7,9,8,10,s)
        rect(5,12,10,12,black)
        for x in (6,8,10):rect(x,11,x,12,white)
        if kind=='zombie':rect(3,3,7,4,s);rect(11,10,12,12,s)
        else: poly([(2,4),(3,1),(12,1),(14,4),(12,5),(3,5)],s)
    elif kind=='spider':
        for y in (4,7,10,13):
            d.line([(4,y),(1,y-2),(0,y)],fill=o,width=2);d.line([(11,y),(14,y-2),(15,y)],fill=o,width=2)
        d.ellipse((3,1,12,14),fill=o);d.ellipse((4,2,11,13),fill=b);rect(5,3,10,6,s)
        for x,y in [(5,7),(7,6),(9,6),(10,8),(6,9),(8,9)]:rect(x,y,x,y,a)
        rect(5,12,5,14,white);rect(10,12,10,14,white)
    elif kind=='beetle':
        poly([(1,4),(3,3),(5,1),(10,1),(13,4),(14,11),(11,14),(4,14),(1,11)],o)
        poly([(3,4),(6,2),(9,2),(12,5),(12,10),(10,13),(5,13),(3,10)],b)
        rect(7,3,8,11,s);rect(4,5,5,9,a);rect(10,5,11,9,a);eye(5,10);eye(9,10)
        d.line([(5,3),(2,0)],fill=a);d.line([(10,3),(13,0)],fill=a)
    elif kind=='wraith':
        poly([(7,0),(12,2),(15,7),(13,14),(10,11),(8,15),(5,12),(1,14),(0,7),(3,2)],o)
        poly([(7,1),(12,3),(14,7),(12,12),(10,9),(8,13),(5,10),(2,12),(1,7),(4,3)],s)
        poly([(4,5),(6,3),(10,4),(12,7),(10,10),(5,10),(3,7)],b);eye(5,6);eye(10,6);rect(7,9,8,10,a)
    elif kind=='mushroom':
        poly([(0,7),(2,3),(6,1),(10,1),(14,4),(15,8),(11,10),(11,14),(4,14),(4,10),(0,9)],o)
        poly([(1,7),(3,4),(6,2),(10,2),(13,5),(14,8),(1,8)],b);rect(5,9,10,13,s)
        for x,y in [(4,5),(9,3),(11,6)]:rect(x,y,x+1,y,a)
        eye(5,10);eye(9,10)
    elif kind in ('goblin','orc','hood','shaman','demon'):
        if kind=='demon':poly([(1,0),(5,3),(6,5),(10,5),(11,3),(14,0),(14,7),(1,7)],s)
        else:poly([(0,3),(5,5),(10,5),(15,3),(13,10),(2,10)],o);poly([(1,4),(5,6),(4,9),(2,8)],s);poly([(14,4),(10,6),(11,9),(13,8)],s)
        face()
        if kind=='hood':poly([(1,7),(3,2),(7,0),(12,2),(14,7),(11,5),(5,5)],s)
        if kind=='shaman':rect(4,2,11,4,s);rect(7,2,8,5,a)
        if kind!='demon':rect(4,11,5,12,white);rect(10,11,11,12,white)
        else:rect(6,11,9,11,a)
    elif kind=='eye':
        poly([(0,7),(3,3),(6,1),(10,1),(13,4),(15,7),(12,12),(8,14),(4,12)],o)
        poly([(1,7),(4,4),(7,2),(10,3),(14,7),(11,11),(7,13),(3,10)],b)
        d.ellipse((4,4,11,11),fill=s);d.ellipse((5,5,10,10),fill=a);rect(7,5,8,10,black);rect(6,5,6,6,white)
        for x,y in [(1,2),(14,2),(1,12),(14,12)]:rect(x,y,x,y,a)
    else:
        face();rect(6,5,9,5,a);rect(9,6,9,8,a);rect(7,8,8,9,a);rect(7,11,8,11,a)
    return im


def main():
    width=6*16;height=math.ceil(len(TILES)/6)*16
    atlas=Image.new('RGBA',(width,height));tiles=[];runs={}
    for i,(name,kind,b,s,a) in enumerate(TILES):
        x,y=(i%6)*16,(i//6)*16;im=sprite(kind,b,s,a);atlas.paste(im,(x,y));tiles.append({'name':name,'x':x,'y':y,'size':16})
        data=[]
        for yy in range(16):
            xx=0
            while xx<16:
                px=im.getpixel((xx,yy));end=xx+1
                while end<16 and im.getpixel((end,yy))==px:end+=1
                if px[3]:data.append((xx,yy,end-xx,('%02x%02x%02x'%px[:3])))
                xx=end
        runs[name]=data
    atlas.save(OUT/'atlas.png',optimize=True)
    (OUT/'catalog.json').write_text(json.dumps({'width':width,'height':height,'tileSize':16,'tiles':tiles},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    # Tiles are data only, no user-controlled code. Pixel runs reproduce the atlas exactly.
    lines=['-- Generated by system/tools/build_monster_icon_atlas.py. Do not edit.','return table.freeze({']
    for name,items in runs.items():
        lines.append('    ['+json.dumps(name)+'] = table.freeze({')
        lines.extend('        {%d,%d,%d,"%s"},'%item for item in items)
        lines.append('    }),')
    lines.append('})')
    (ROOT/'src/shared/interface/MonsterIconAtlas.luau').write_text('\n'.join(lines)+'\n',encoding='utf8')
if __name__=='__main__':main()

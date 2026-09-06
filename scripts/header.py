# Renders header.gif: Doom-style flame with sand grains that fall into the name.
# Run: uv run --with pillow python scripts/header.py
import random, math, sys
from PIL import Image, ImageDraw, ImageFont
random.seed(7)
import os; S=os.path.dirname(os.path.abspath(__file__))
name=[l.rstrip('\n') for l in open(f'{S}/name.txt')]
name=[l for l in name if l.strip()]
NW=max(len(l) for l in name); NH=len(name)
COLS,ROWS=NW+8,NH+10
OX=(COLS-NW)//2; OY=3
FPS=15; BUILD=int(7*FPS); HOLD=int(4*FPS); TOTAL=BUILD+HOLD
FS=13
font=ImageFont.truetype('/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf',FS)
bold=ImageFont.truetype('/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Bold.ttf',FS)
bb=font.getbbox('█'); CW=bb[2]-bb[0]; CH=int(FS*1.25)
PAD=10
W=COLS*CW+PAD*2; H=ROWS*CH+PAD*2
BG=(26,27,39); LET=(192,202,245); SHD=(122,162,247); SANDC=(224,175,104)
# targets
GROUND=(158,206,106); WALL=(224,175,104)
targets=[]  # (x, y, char, color)
for r,l in enumerate(name):
    for c,ch in enumerate(l):
        if ch!=' ': targets.append((OX+c,OY+r,ch,LET if ch=='█' else SHD))
for x in range(COLS):
    targets.append((x,ROWS-1,'GROUND_'[x%7],GROUND))
    targets.append((x,0,'GROUND_'[x%7],GROUND))
for y in range(1,ROWS-1):
    targets.append((0,y,'WALL'[y%4],WALL))
    targets.append((COLS-1,y,'WALL'[y%4],WALL))
# spawn schedule: lower rows first, with jitter, whole build fits in BUILD minus fall time
fall=ROWS
grains=[]
for (tx,ty,ch,col) in targets:
    depth=(ROWS-1)-ty  # 0 for bottom row
    spawn=int(depth*(BUILD-fall-20)/ROWS)+random.randint(0,18)
    sx=max(0,min(COLS-1,tx+random.randint(-10,10)))
    grains.append(dict(tx=tx,ty=ty,ch=ch,col=col,spawn=spawn,x=sx,y=-1,landed=False,fc=random.choice('sand')))
# flame
flame='...::/\\/\\/\\+=*abcdef01XYZ#'
data=[0]*(COLS*ROWS)
def rndi(a,b): return random.randint(a,b)
def vnoise():
    tbl=256; r=[random.random() for _ in range(tbl)]; p=list(range(tbl)); random.shuffle(p); p=p+p
    def ss(t): return t*t*(3-2*t)
    def f(px,py):
        xi,yi=math.floor(px),math.floor(py); tx,ty=px-xi,py-yi
        rx0,rx1,ry0,ry1=xi%tbl,(xi+1)%tbl,yi%tbl,(yi+1)%tbl
        c00=r[p[p[rx0]+ry0]];c10=r[p[p[rx1]+ry0]];c01=r[p[p[rx0]+ry1]];c11=r[p[p[rx1]+ry1]]
        sx,sy=ss(tx),ss(ty)
        nx0=c00+(c10-c00)*sx; nx1=c01+(c11-c01)*sx
        return nx0+(nx1-nx0)*sy
    return f
noise=vnoise()
def flame_step(t):
    last=COLS*(ROWS-1)
    for i in range(COLS):
        val=int(6+noise(i*0.05,t)*(28))
        data[last+i]=min(val,data[last+i]+2)
    for i in range(len(data)):
        row=i//COLS; col=i%COLS
        dest=row*COLS+max(0,min(COLS-1,col+rndi(-1,1)))
        src=min(ROWS-1,row+1)*COLS+col
        data[dest]=max(0,data[src]-rndi(0,3))
def fcol(u):
    t=min(1,u/28)
    stops=[(70,30,40),(150,50,40),(230,110,50),(255,158,100),(255,220,150)]
    x=t*(len(stops)-1); i=min(int(x),len(stops)-2); f=x-i
    a,b=stops[i],stops[i+1]
    return tuple(int(a[k]+(b[k]-a[k])*f) for k in range(3))
frames=[]
for fr in range(TOTAL):
    flame_step(fr*0.05)
    img=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(img)
    # flame layer
    for i,u in enumerate(data):
        if u<=0: continue
        r,c=divmod(i,COLS)
        d.text((PAD+c*CW,PAD+r*CH),flame[min(u,len(flame)-1)],font=font,fill=fcol(u))
    # grains
    for g in grains:
        if fr<g['spawn']: continue
        if not g['landed']:
            g['y']+=1
            dx=g['tx']-g['x']; left=g['ty']-g['y']
            if dx!=0 and (left<=abs(dx) or random.random()<0.6): g['x']+=1 if dx>0 else -1
            if g['y']>=g['ty']: g['landed']=True; g['x']=g['tx']; g['y']=g['ty']
            if not g['landed']:
                if random.random()<0.3: g['fc']=random.choice('sand')
                d.rectangle((PAD+g['x']*CW,PAD+g['y']*CH,PAD+g['x']*CW+CW,PAD+g['y']*CH+CH),fill=BG)
                d.text((PAD+g['x']*CW,PAD+g['y']*CH),g['fc'],font=font,fill=SANDC)
                continue
        x,y=g['tx'],g['ty']
        d.rectangle((PAD+x*CW,PAD+y*CH,PAD+x*CW+CW,PAD+y*CH+CH),fill=BG)
        if g['ch']=='█': d.rectangle((PAD+x*CW,PAD+y*CH,PAD+x*CW+CW,PAD+y*CH+CH),fill=g['col'])
        else: d.text((PAD+x*CW,PAD+y*CH),g['ch'],font=bold,fill=g['col'])
    frames.append(img.quantize(colors=48,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE))
frames[0].save(os.path.join(S,'..','header.gif'),save_all=True,append_images=frames[1:],duration=int(1000/FPS),optimize=True)  # no loop: plays once, holds last frame
print(W,H,TOTAL)

#!/usr/bin/env python3
"""SC019: experimental adaptive RGB565 subpixel reconstruction, not HQ2x or MMPX."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'PSYCH,VIVID };','PSYCH,VIVID,HD_PIXEL,HD_INK };')
s=rep(s,'"PSYCH","VIVID"};','"PSYCH","VIVID","HD PIXEL","HD INK"};')
s=rep(s,'edgeScale=mode==SMOOTH||mode==OUTLINE||mode==COMIC||mode==CRT;',
'edgeScale=mode==SMOOTH||mode==OUTLINE||mode==COMIC||mode==CRT||mode==HD_PIXEL||mode==HD_INK;')
s=rep(s,'outlineMode=mode==OUTLINE||mode==COMIC;','outlineMode=mode==OUTLINE||mode==COMIC||mode==HD_INK;')
s=rep(s,'static int oldIndexedW=0,',r'''// Distance is measured in comparable 5-bit RGB component units.
static inline int hdDistance(uint16_t a,uint16_t b){
    return abs(int(a>>11)-int(b>>11))+
           abs(int((a>>6)&31)-int((b>>6)&31))+
           abs(int(a&31)-int(b&31));
}
static inline uint16_t hdHalf(uint16_t a,uint16_t b){
    return uint16_t((a&b)+(((a^b)&0xf7de)>>1));
}
static inline uint16_t hdCorner(uint16_t e,uint16_t nx,uint16_t ny,uint16_t ox,uint16_t oy){
    if(nx==e||ny==e)return e;
    if(nx!=ny&&hdDistance(nx,ny)>6)return e;
    // Do not round one-pixel lines or uniform opposing edges.
    if(hdDistance(nx,ox)<=6||hdDistance(ny,oy)<=6)return e;
    uint16_t target=hdHalf(nx,ny);
    // Exact matching corners may receive a stronger blend; near matches are subtle.
    uint16_t mid=hdHalf(e,target);
    return nx==ny?mid:hdHalf(e,mid);
}
static int oldIndexedW=0,''')
s=rep(s,'                        scaled[x]=localPal[v];',r'''                        scaled[x]=localPal[v];
                        if((visualMode==HD_PIXEL||visualMode==HD_INK)&&sy*200<h*144){
                            const uint16_t center=localPal[e];
                            const uint16_t nx=localPal[(q&1)?f:d],ny=localPal[half?hpx:b];
                            const uint16_t ox=localPal[(q&1)?d:f],oy=localPal[half?b:hpx];
                            scaled[x]=hdCorner(center,nx,ny,ox,oy);
                        }''')
# Four columns, 11 modes; the final cell is inert. Keep original release/tap semantics.
s=rep(s,'for(int i=0;i<9;i++)button((i%3)*160,top+42+(i/3)*66,160,64,visualNames[i],i==visualMode);',
'for(int i=0;i<11;i++)button((i%4)*120,top+42+(i/4)*66,120,64,visualNames[i],i==visualMode);')
s=rep(s,'if(x>=340&&x<480&&y>=top&&y<top+38)return 9;',
'if(x>=340&&x<480&&y>=top&&y<top+38)return 11;')
s=rep(s,'return (y-top-42)%66<64?r*3+x/160:-1;',
'int i=r*4+x/120;return (y-top-42)%66<64&&i<11?i:-1;')
s=rep(s,'if(choice>=0&&choice<9){setVisual(VisualMode(choice));done=true;}',
'if(choice>=0&&choice<11){setVisual(VisualMode(choice));done=true;}')
s=rep(s,'else if(choice==9)done=true;','else if(choice==11)done=true;')
p.write_text(s.replace("SC017","SC019"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC017","SC019"))
# Verify packed RGB565 averaging on all component values and extremes.
def mix(a,b): return (a&b)+(((a^b)&0xf7de)>>1)
for shift,count in ((0,32),(5,64),(11,32)):
    for a in range(count):
        for b in range(count):
            assert mix(a<<shift,b<<shift)==((a+b)//2)<<shift
assert mix(0xffff,0)==0x7bef
print("SC019: HD PIXEL and HD INK, virtual 2x subpixel grid, verified RGB565 averaging, 11 touch presets")

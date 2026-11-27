#!/usr/bin/env python3
"""SC015: optional palette-preserving EPX smoothing, original scaler fallback."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
p=src/"main.cpp";s=p.read_text()
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
s=rep(s,'static bool indexedValid=false;','''static bool indexedValid=false;
static bool edgeScale=true;
static uint8_t edgeDirty[240],edgeAbove[320],edgeBelow[320];
static uint16_t edgeX[480],edgeY[480];
extern "C" void prisma_filter_set(bool enabled){
    if(edgeScale!=enabled){edgeScale=enabled;indexedValid=false;}
}
''')
s=rep(s,'extern "C" void prisma_diag_poll(){','extern "C" void prisma_filter_set(bool);\nextern "C" void prisma_diag_poll(){')
s=rep(s,'            else if(!strcmp(line,":end"))scTestEnd();','''            else if(!strcmp(line,":pixel")){prisma_filter_set(false);Serial.println("VIDEO PIXEL");}
            else if(!strcmp(line,":smooth")){prisma_filter_set(true);Serial.println("VIDEO EDGE");}
            else if(!strcmp(line,":end"))scTestEnd();''')
s=rep(s,'        for(int x=0;x<480;x++)xmapFull[x]=x*w/480;','''        for(int x=0;x<480;x++){
            xmapFull[x]=x*w/480;
            edgeX[x]=x*2*w/480;
            edgeY[x]=x*2*h/480;
        }''')
a=s.index('    for(int sy=0;sy<h;sy++){',s.index('unsigned dirty=0,written=0;'))
b=s.index('    oldIndexedW=w;',a)
original=s[a:b]
smooth=r'''    if(edgeScale){
        // First collect all dirty rows before overwriting the prior indices.
        // EPX samples the adjacent rows, so both neighbours need invalidation.
        for(int sy=0;sy<h;sy++)edgeDirty[sy]=force||memcmp(prev+sy*w,pixels+sy*w,w)!=0;
        for(int sy=0;sy<h;sy++){
            const bool sourceChanged=edgeDirty[sy]||(sy>0&&edgeDirty[sy-1])||(sy+1<h&&edgeDirty[sy+1]);
            const bool cursorNow=visible&&sy>=cy&&sy<cy+ch;
            const bool cursorBefore=indexedValid&&sy>=oldCursorY&&sy<oldCursorY+oldCursorH;
            if(!sourceChanged&&!cursorNow&&!cursorBefore)continue;
            memcpy(localIndices,pixels+sy*w,w);
            memcpy(edgeAbove,pixels+(sy?sy-1:sy)*w,w);
            memcpy(edgeBelow,pixels+(sy+1<h?sy+1:sy)*w,w);
            memcpy(prev+sy*w,localIndices,w);
            const int lo=cursorNow?max(0,cx):0,hi=cursorNow?min(w,cx+cw):0;
            bool changed=false;int lastHalf=-1;
            for(int y=yedge[sy];y<yedge[sy+1];y++){
                const int half=edgeY[y]&1;
                if(half!=lastHalf){
                    for(int x=0;x<480;x++){
                        const int q=edgeX[x],sx=q>>1;
                        const uint8_t e=localIndices[sx],b=edgeAbove[sx],hpx=edgeBelow[sx];
                        const uint8_t d=localIndices[sx?sx-1:sx],f=localIndices[sx+1<w?sx+1:sx];
                        uint8_t v=e;
                        // Scale2x/EPX: choose an existing palette index only
                        // when two neighbouring edges agree.
                        if(b!=hpx&&d!=f){
                            if(!half&&!(q&1)&&d==b)v=d;
                            if(!half&&(q&1)&&b==f)v=f;
                            if(half&&!(q&1)&&d==hpx)v=d;
                            if(half&&(q&1)&&hpx==f)v=f;
                        }
                        scaled[x]=localPal[v];
                        // Mouse retains original nearest-neighbour footprint.
                        if(sx>=lo&&sx<hi){
                            const uint8_t m=mouse[(sy-cy)*cw+sx-cx];
                            if(m!=key)scaled[x]=localCursorPal[m];
                        }
                    }
                    lastHalf=half;
                }
                if(fb){
                    uint16_t* dst=fb+y*480;
                    if(!sourceChanged&&!memcmp(dst,scaled,sizeof(scaled)))continue;
                    memcpy(dst,scaled,sizeof(scaled));
                }else lcd.draw16bitRGBBitmap(0,y,scaled,480,1);
                changed=true;written+=480;
            }
            if(changed)dirty++;
        }
    }else{
'''
s=s[:a]+smooth+original+'    }\n'+s[b:]
p.write_text(s.replace("SC014","SC015"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC014","SC015"))
# Check that both filters retain the original physical-pixel touch geometry.
for n in range(1,321):
    assert all((x*2*n//480)//2==x*n//480 for x in range(480))
print("SC015: direct palette-preserving EPX, neighbour dirty rows, :pixel fallback, :smooth re-enable")

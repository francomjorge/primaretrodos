#!/usr/bin/env python3
"""SC022: actual MMPX C99 rules, adapted to a two-output-row interface.
Independent of SC021 painterly branch; SC020 is the compiled baseline.
"""
from pathlib import Path
import sys,subprocess,tempfile
src=Path(sys.argv[1])/"src"
vendor=Path(__file__).resolve().parents[1]/"third_party/mmpx"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
original=(vendor/"mmpx.c").read_text()
# Upstream typo: comparing min to max never clamps positive overflow.
# Retain all slope/intersection rules. Fix signed neighbor coordinates.
fixed=rep(original,"min > max ? max : v","v > max ? max : v")
fixed=rep(fixed,"uint32_t srcX = 0;","int srcX = 0;")
fixed=rep(fixed,"for (uint32_t srcY = 0;","for (int srcY = 0;")
a=fixed.index("    return (struct Meta)");b=fixed.index("    };",a)+len("    };")
fixed=fixed[:a]+"    return Meta{srcBuffer,srcWidth,srcHeight,srcWidth-1,srcHeight-1};"+fixed[b:]
row=rep(fixed,"void mmpx_scale2x(const uint32_t* srcBuffer, uint32_t* dst, int srcWidth, int srcHeight)","static void scaleRow(const uint32_t* srcBuffer, uint32_t* dst, int srcWidth, int srcHeight,int srcY)")
row=rep(row,"    for (int srcY = 0; srcY < srcHeight; ++srcY)","    if(srcY>=0&&srcY<srcHeight)")
row=rep(row,"((srcX + srcX) + (srcY << 2) * srcWidth) >> 0","uint32_t(srcX * 2)")
def wrap(code,ns):
    return "#pragma once\n#include <stdint.h>\n#include <stdbool.h>\nnamespace "+ns+" {\n"+code+"\n}\n"
(src/"prisma_mmpx022.h").write_text(wrap(row,"PrismaMmpx"))
(src/"MMPX-LICENSE.txt").write_text((vendor/"LICENSE").read_text())
# Host fixture compares the adapted row output byte-for-byte to the full
# reference with the same border-clamp fix, including 1x1 and odd sizes.
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp)
    (d/"reference.h").write_text(wrap(fixed,"Reference"))
    (d/"row.h").write_text(wrap(row,"PrismaMmpx"))
    (d/"test.cpp").write_text(r'''
#include "reference.h"
#include "row.h"
#include <vector>
#include <cassert>
#include <random>
int main(){
    std::mt19937 rng(22);
    for(int h: {1,2,3,7,17,32})for(int w:{1,2,5,16,31,320}){
        std::vector<uint32_t> in(w*h),out(4*w*h),rows(4*w*h);
        for(int pattern=0;pattern<4;pattern++){
            for(int y=0;y<h;y++)for(int x=0;x<w;x++){
                unsigned k=pattern==0?0:pattern==1?(x+y)%3:pattern==2?unsigned(x>y):rng()%16;
                in[y*w+x]=k*0x0c0c0c;
            }
            Reference::mmpx_scale2x(in.data(),out.data(),w,h);
            for(int y=0;y<h;y++)PrismaMmpx::scaleRow(in.data(),rows.data()+4*w*y,w,h,y);
            assert(out==rows);
        }
    }
}
''')
    subprocess.run(["g++","-std=c++11","-O2",str(d/"test.cpp"),"-o",str(d/"test")],check=True)
    subprocess.run([str(d/"test")],check=True)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'#include "monkey_cover016.h"','#include "monkey_cover016.h"\n#include "prisma_mmpx022.h"')
s=rep(s,'HD_PIXEL,HD_INK };','HD_PIXEL,HD_INK,MMPX };')
s=rep(s,'"HD PIXEL","HD INK"};','"HD PIXEL","HD INK","MMPX"};')
s=rep(s,'static VisualMode visualMode=SMOOTH;','''static VisualMode visualMode=SMOOTH;
static uint32_t* mmpxSource=nullptr;
static uint32_t mmpxRows[4*320];
static uint32_t mmpxPalette[256];
static inline uint32_t mmpxRGB888(uint16_t c){
    unsigned r=c>>11,g=(c>>5)&63,b=c&31;
    return ((r<<3|r>>2)<<16)|((g<<2|g>>4)<<8)|(b<<3|b>>2);
}
static inline uint16_t mmpxRGB565(uint32_t c){
    return uint16_t(((c>>19)&31)<<11|((c>>10)&63)<<5|((c>>3)&31));
}
''')
s=rep(s,'||mode==HD_PIXEL||mode==HD_INK;','||mode==HD_PIXEL||mode==HD_INK||mode==MMPX;')
s=rep(s,'    visualMode=mode;\n    edgeScale=', '''    if(mode!=MMPX&&mmpxSource){free(mmpxSource);mmpxSource=nullptr;}
    visualMode=mode;
    edgeScale=''')
# Explicit serial pixel/smooth/outline also release scratch memory.
s=rep(s,'visualMode=enabled?SMOOTH:PIXEL;','if(mmpxSource){free(mmpxSource);mmpxSource=nullptr;}\n    visualMode=enabled?SMOOTH:PIXEL;')
s=rep(s,'visualMode=OUTLINE;edgeScale=true;','if(mmpxSource){free(mmpxSource);mmpxSource=nullptr;}\n    visualMode=OUTLINE;edgeScale=true;')
s=rep(s,'    if(edgeScale){\n        // First collect','''    if(visualMode==MMPX&&!mmpxSource){
        mmpxSource=(uint32_t*)heap_caps_malloc(320*240*4,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        if(!mmpxSource){setVisual(SMOOTH);labBarDirty=true;prisma_diag_line(2,"MMPX BUFFER UNAVAILABLE");}
        force=true;
    }
    if(edgeScale){
        // First collect''')
s=rep(s,'        for(int sy=0;sy<h;sy++)edgeDirty[sy]=force||memcmp(prev+sy*w,pixels+sy*w,w)!=0;',r'''        for(int sy=0;sy<h;sy++)edgeDirty[sy]=force||memcmp(prev+sy*w,pixels+sy*w,w)!=0;
        if(visualMode==MMPX){
            if(force)for(int i=0;i<256;i++)mmpxPalette[i]=mmpxRGB888(localPal[i]);
            for(int sy=0;sy<h;sy++)if(edgeDirty[sy]){
                const uint8_t* input=pixels+sy*w;
                uint32_t* output=mmpxSource+sy*w;
                for(int x=0;x<w;x++)output[x]=mmpxPalette[input[x]];
            }
        }''')
s=rep(s,'            const bool sourceChanged=edgeDirty[sy]||(sy>0&&edgeDirty[sy-1])||(sy+1<h&&edgeDirty[sy+1]);',r'''            bool sourceChanged=edgeDirty[sy]||(sy>0&&edgeDirty[sy-1])||(sy+1<h&&edgeDirty[sy+1]);
            if(visualMode==MMPX)for(int d=2;d<=3;d++)
                sourceChanged=sourceChanged||(sy>=d&&edgeDirty[sy-d])||(sy+d<h&&edgeDirty[sy+d]);''')
s=rep(s,'            const int lo=cursorNow?max(0,cx):0,hi=cursorNow?min(w,cx+cw):0;',r'''            if(visualMode==MMPX)PrismaMmpx::scaleRow(mmpxSource,mmpxRows,w,h,sy);
            const int lo=cursorNow?max(0,cx):0,hi=cursorNow?min(w,cx+cw):0;''')
s=rep(s,'                        scaled[x]=localPal[v];','                        scaled[x]=visualMode==MMPX?mmpxRGB565(mmpxRows[half*2*w+q]):localPal[v];')
# 12 presets + LAB. Use 5-column grid, keep LAB in the next cell.
s=rep(s,'for(int i=0;i<visualCount;i++)button((i%4)*120,top+42+(i/4)*66,120,64,visualNames[i],i==visualMode);',
'for(int i=0;i<visualCount;i++)button((i%5)*96,top+42+(i/5)*66,96,64,visualNames[i],i==visualMode);')
s=rep(s,'button(360,top+174,120,64,"LAB",labActive);','button(192,top+174,96,64,"LAB",labActive);')
s=rep(s,'if(x>=340&&x<480&&y>=top&&y<top+38)return 12;','if(x>=340&&x<480&&y>=top&&y<top+38)return visualCount+1;')
s=rep(s,'int i=r*4+x/120;return (y-top-42)%66<64&&i<12?i:-1;','int i=r*5+x/96;return (y-top-42)%66<64&&i<=visualCount?i:-1;')
s=rep(s,'else if(choice==11){setLab(true);done=true;}','else if(choice==visualCount){setLab(true);done=true;}')
s=rep(s,'else if(choice==12)done=true;','else if(choice==visualCount+1)done=true;')
a=s.index('extern "C" void prisma_visual_menu(){');b=s.index('static volatile bool runtimeActive=false;',a)
t=s[a:b]
t=rep(t,'lcd.setTextColor(0xffff);lcd.setTextSize(2);\n        lcd.setCursor(x+(w-int(strlen(label))*12)/2,y+(h-16)/2);lcd.print(label);',
'''int sz=int(strlen(label))*12<=w-8?2:1;
        lcd.setTextColor(0xffff);lcd.setTextSize(sz);
        lcd.setCursor(x+(w-int(strlen(label))*6*sz)/2,y+(h-8*sz)/2);lcd.print(label);''')
s=s[:a]+t+s[b:]
p.write_text(s.replace("SC020","SC022"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC020","SC022"))
print("SC022: original MMPX rules, corrected border clamp, host row equivalence fixtures, 3-row dependency halo, 12 live presets")

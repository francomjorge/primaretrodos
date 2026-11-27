#!/usr/bin/env python3
"""SC023: reuse native ScummVM HQ2x, Super2xSaI and SuperEagle with bounded row buffers."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
base=src/"native/components/graphics/scaler"
# Keep HQ2x's upstream 256-pattern switch and interpolation rules. The original
# 65536-entry YUV LUT would consume 256 KiB; indexed input uses at most 256
# distinct colors. Build a small open-addressed cache with exact upstream YUV.
p=base/"hq2x.cpp";s=p.read_text()
s=rep(s,'extern "C" uint32   *RGBtoYUV;\n#define YUV(x)\tRGBtoYUV[w ## x]',r'''struct PrismaYUVSlot { uint32 key,value; };
static PrismaYUVSlot prismaYuv[512];
extern "C" void prisma_hq_palette(const uint16* colors){
    // Zero key denotes empty; actual RGB565 key is color+1.
    for(unsigned i=0;i<512;i++)prismaYuv[i].key=0;
    for(unsigned i=0;i<256;i++){
        unsigned c=colors[i],key=c+1;
        unsigned slot=((c*2654435761u)>>23)&511;
        while(prismaYuv[slot].key&&prismaYuv[slot].key!=key)slot=(slot+1)&511;
        uint8 r,g,b;
        Graphics::createPixelFormat<565>().colorToRGB(c,r,g,b);
        int y=(r+g+b)>>2,u=128+((int(r)-int(b))>>2),v=128+((-int(r)+2*int(g)-int(b))>>3);
        prismaYuv[slot].value=(y<<16)|(u<<8)|v;
        prismaYuv[slot].key=key;
    }
}
static inline uint32 prismaYUV(uint16 c){
    unsigned key=unsigned(c)+1,slot=((unsigned(c)*2654435761u)>>23)&511;
    while(prismaYuv[slot].key){
        if(prismaYuv[slot].key==key)return prismaYuv[slot].value;
        slot=(slot+1)&511;
    }
    // Defensive path for any non-palette color.
    uint8 r,g,b;
    Graphics::createPixelFormat<565>().colorToRGB(c,r,g,b);
    int y=(r+g+b)>>2,u=128+((int(r)-int(b))>>2),v=128+((-int(r)+2*int(g)-int(b))>>3);
    return (y<<16)|(u<<8)|v;
}
#define YUV(x) prismaYUV(w ## x)''')
# Native ScummVM source, not Arduino-facing headers. Explicit include for PixelFormat.
s=rep(s,'#include "graphics/scaler/intern.h"','#include "graphics/scaler/intern.h"\n#include "graphics/pixelformat.h"')
p.write_text(s)
p=base/"2xsai.cpp";s=p.read_text()
s+=r'''
// PRISMA uses existing portable C++ routines at RGB565 and a padded 4-row window.
extern void HQ2x(const uint8*,uint32,uint8*,uint32,int,int);
extern "C" void prisma_native_scale(int mode,const uint16* in,unsigned pitch,uint16* out,int w){
    extern int gBitFormat;
    gBitFormat=565;
    if(mode==0)Super2xSaI((const uint8*)in,pitch*2,(uint8*)out,w*4,w,1);
    else if(mode==1)SuperEagle((const uint8*)in,pitch*2,(uint8*)out,w*4,w,1);
    else HQ2x((const uint8*)in,pitch*2,(uint8*)out,w*4,w,1);
}
'''
p.write_text(s)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'HD_PIXEL,HD_INK,MMPX };','HD_PIXEL,HD_INK,MMPX,SUPER_SAI,SUPER_EAGLE,HQ2X };')
s=rep(s,'"HD PIXEL","HD INK","MMPX"};','"HD PIXEL","HD INK","MMPX","SUPER SAI","EAGLE","HQ2X"};')
s=rep(s,'static VisualMode visualMode=SMOOTH;',r'''static VisualMode visualMode=SMOOTH;
extern "C" void prisma_native_scale(int,const uint16_t*,unsigned,uint16_t*,int);
extern "C" void prisma_hq_palette(const uint16_t*);
static uint16_t nativeScaleIn[4][323],nativeScaleOut[4*320];
static bool isNativeScaler(){return visualMode==SUPER_SAI||visualMode==SUPER_EAGLE||visualMode==HQ2X;}
''')
s=rep(s,'||mode==HD_PIXEL||mode==HD_INK||mode==MMPX;','||mode==HD_PIXEL||mode==HD_INK||mode==MMPX||mode==SUPER_SAI||mode==SUPER_EAGLE||mode==HQ2X;')
s=rep(s,'    if(memcmp(previousPal,localPal,sizeof(localPal)))force=true;','    if(memcmp(previousPal,localPal,sizeof(localPal)))force=true;\n    if(visualMode==HQ2X&&force)prisma_hq_palette(localPal);')
s=rep(s,'            if(visualMode==MMPX)for(int d=2;d<=3;d++)','            if(isNativeScaler()&&sy+2<h&&edgeDirty[sy+2])sourceChanged=true;\n            if(visualMode==MMPX)for(int d=2;d<=3;d++)')
s=rep(s,'            if(visualMode==MMPX)PrismaMmpx::scaleRow(mmpxSource,mmpxRows,w,h,sy);',r'''            if(visualMode==MMPX)PrismaMmpx::scaleRow(mmpxSource,mmpxRows,w,h,sy);
            if(isNativeScaler()){
                for(int k=0;k<4;k++){
                    const uint8_t* input=pixels+max(0,min(h-1,sy+k-1))*w;
                    auto* dst=nativeScaleIn[k];
                    for(int x=0;x<w;x++)dst[x+1]=localPal[input[x]];
                    dst[0]=dst[1];dst[w+1]=dst[w];dst[w+2]=dst[w];
                }
                int mode=visualMode==SUPER_SAI?0:visualMode==SUPER_EAGLE?1:2;
                prisma_native_scale(mode,&nativeScaleIn[1][1],323,nativeScaleOut,w);
            }''')
s=rep(s,'scaled[x]=visualMode==MMPX?mmpxRGB565(mmpxRows[half*2*w+q]):localPal[v];',
'scaled[x]=isNativeScaler()?nativeScaleOut[half*2*w+q]:visualMode==MMPX?mmpxRGB565(mmpxRows[half*2*w+q]):localPal[v];')
# 15 presets + LAB: four-by-four. Keep the same modal top/bottom and touch rules.
s=rep(s,'for(int i=0;i<visualCount;i++)button((i%5)*96,top+42+(i/5)*66,96,64,visualNames[i],i==visualMode);',
'for(int i=0;i<visualCount;i++)button((i%4)*120,top+42+(i/4)*49,120,47,visualNames[i],i==visualMode);')
s=rep(s,'button(192,top+174,96,64,"LAB",labActive);','button(360,top+189,120,47,"LAB",labActive);')
s=rep(s,'int r=(y-top-42)/66;\n        int i=r*5+x/96;return (y-top-42)%66<64&&i<=visualCount?i:-1;',
'int r=(y-top-42)/49;\n        int i=r*4+x/120;return (y-top-42)%49<47&&i<=visualCount?i:-1;')
p.write_text(s.replace("SC022","SC023"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC022","SC023"))
# Host bounds fixture for the exact row layout, output width and touch grid.
for w in range(1,321):
    for x in (0,w-1):
        for dx in (-1,0,1,2):
            for dy in (-1,0,1,2):
                index=(1+dy)*323+1+x+dx
                assert 0<=index<4*323
        assert 2*w+2*x+1<4*320
assert 42+3*49+47<=240
assert 4*4==15+1
print("SC023: original native Super2xSaI, SuperEagle, HQ2x; 15 filters; padded row window and compact exact YUV palette cache")

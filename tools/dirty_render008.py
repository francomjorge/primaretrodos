#!/usr/bin/env python3
"""SC008: fused indexed palette + fullscreen scaling, dirty rows and timing.
Keep SC007 controls, SC003 LCD setup and the original engine unchanged."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
p=src/"main.cpp"
s=p.read_text()
anchor='extern "C" void prisma_lcd_flush(){'
assert s.count(anchor)==1
s=s.replace(anchor,'''static bool indexedValid=false;
static int oldIndexedW=0,oldIndexedH=0,oldCursorY=0,oldCursorH=0;
static uint16_t previousPal[256],previousCursorPal[256];
static uint16_t localPal[256],localCursorPal[256];
static uint16_t xmapFull[480],yedge[241],scaled[480];
static uint8_t localIndices[320];
static uint32_t renderCalls=0,renderPresents=0,renderRows=0,renderPixels=0;
static uint64_t renderWork=0,renderFlush=0;
static uint32_t perfAt=0;
extern "C" void prisma_present_indexed(const uint8_t* pixels,int w,int h,
    const uint16_t* palette,const uint8_t* mouse,int cx,int cy,int cw,int ch,
    uint32_t key,const uint16_t* cursorPalette){
    if(!nativeFrame||!pixels||!palette||!cursorPalette||w<1||w>320||h<1||h>240)return;
    const uint32_t begin=micros();
    frameW=w;frameH=h;
    bool force=!indexedValid||oldIndexedW!=w||oldIndexedH!=h;
    if(force){
        for(int x=0;x<480;x++)xmapFull[x]=x*w/480;
        // First output row whose nearest-neighbour source coordinate is sy.
        for(int sy=0;sy<=h;sy++)yedge[sy]=(sy*480+h-1)/h;
    }
    // Preserve the exact SC004 RGB565 conversion.
    for(int i=0;i<256;i++){localPal[i]=__builtin_bswap16(palette[i]);localCursorPal[i]=__builtin_bswap16(cursorPalette[i]);}
    if(memcmp(previousPal,localPal,sizeof(localPal)))force=true;
    const bool cursorPalChanged=memcmp(previousCursorPal,localCursorPal,sizeof(localCursorPal))!=0;
    memcpy(previousPal,localPal,sizeof(localPal));
    memcpy(previousCursorPal,localCursorPal,sizeof(localCursorPal));
    const bool visible=mouse&&cw>0&&ch>0&&cw<=320&&ch<=240;
    uint16_t* fb=(lcd.width()==480&&lcd.height()==480&&lcd.getRotation()==0)?lcd.getFramebuffer():nullptr;
    uint8_t* prev=reinterpret_cast<uint8_t*>(nativeFrame);
    unsigned dirty=0,written=0;
    for(int sy=0;sy<h;sy++){
        const uint8_t* input=pixels+sy*w;
        uint8_t* previous=prev+sy*w;
        const bool cursorNow=visible&&sy>=cy&&sy<cy+ch;
        const bool cursorBefore=indexedValid&&sy>=oldCursorY&&sy<oldCursorY+oldCursorH;
        if(!force&&!cursorNow&&!cursorBefore&&!memcmp(previous,input,w))continue;
        memcpy(localIndices,input,w);
        memcpy(previous,localIndices,w);
        const int lo=cursorNow?max(0,cx):0,hi=cursorNow?min(w,cx+cw):0;
        // Direct conversion to the final scaled row, no 16-bit intermediate frame.
        for(int x=0;x<480;x++){
            const int sx=xmapFull[x];
            uint16_t color=localPal[localIndices[sx]];
            if(sx>=lo&&sx<hi){const uint8_t v=mouse[(sy-cy)*cw+sx-cx];if(v!=key)color=localCursorPal[v];}
            scaled[x]=color;
        }
        const int y0=yedge[sy],y1=yedge[sy+1];
        bool changed=false;
        for(int y=y0;y<y1;y++){
            if(fb){
                uint16_t* dst=fb+y*480;
                if(!force&&!memcmp(dst,scaled,sizeof(scaled)))continue;
                memcpy(dst,scaled,sizeof(scaled));
            }else lcd.draw16bitRGBBitmap(0,y,scaled,480,1);
            changed=true;written+=480;
        }
        if(changed)dirty++;
    }
    oldIndexedW=w;oldIndexedH=h;oldCursorY=cy;oldCursorH=visible?ch:0;
    indexedValid=true;
    const uint32_t flushStart=micros();
    if(written){lcd.flush(true);renderPresents++;}
    renderFlush+=micros()-flushStart;
    renderCalls++;renderRows+=dirty;renderPixels+=written;renderWork+=micros()-begin;
    const uint32_t now=millis();if(!perfAt)perfAt=now;
    if(now-perfAt>=3000){
        Serial.printf("SC008 PERF ms=%u requests=%u presents=%u avg_us=%u flush_avg_us=%u dirty_rows=%u lcd_pixels=%u heap=%u psram=%u\\\\n",
            now-perfAt,renderCalls,renderPresents,(unsigned)(renderWork/renderCalls),
            (unsigned)(renderFlush/(renderPresents?renderPresents:1)),renderRows,renderPixels,
            (unsigned)ESP.getFreeHeap(),(unsigned)ESP.getFreePsram());
        renderCalls=renderPresents=renderRows=renderPixels=0;renderWork=renderFlush=0;perfAt=now;
    }
}
'''+anchor,1)
# Legacy raw splash still uses original renderer and invalidates indexed cache.
old='if(frameValid)GameVideo::draw(lcd,nullptr,nullptr,nativeFrame,frameW,frameH,frameW,{layoutMode,false});'
assert s.count(old)==1
s=s.replace(old,'indexedValid=false;\n    '+old)
# No runtime selection, no new task: retain tested ownership and cache flush.
s=s.replace("SC007","SC008")
# Python generated C++ log newline.
s=s.replace('psram=%u\\\\n','psram=%u\\n')
p.write_text(s)
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC007","SC008"))
p=src/"native/components/backends/platform/esp32/osystem-display.cpp"
s=p.read_text()
anchor='extern "C" void prisma_frame_begin(int,int);'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''
extern "C" void prisma_present_indexed(const uint8_t*,int,int,const uint16_t*,
    const uint8_t*,int,int,int,int,uint32_t,const uint16_t*);
''')
a=s.index("void OSystem_Esp32::display_flush(){")
z=s.index("} // namespace _Esp32",a)
s=s[:a]+'''void OSystem_Esp32::display_flush(){
    if(!ready||!_gamePixels||!_gameWidth||_gameWidth>320||!_gameHeight||_gameHeight>240)return;
    const uint16_t* pal=(const uint16_t*)_palette;
    const uint16_t* cp=(const uint16_t*)(_cursorPaletteEnabled?_cursorPalette:_palette);
    const int cx=int(getCursorPosX())-_cursorHotspotX,cy=int(getCursorPosY())-_cursorHotspotY;
    prisma_present_indexed(_gamePixels,_gameWidth,_gameHeight,pal,
        _cursorVisible?_mouseBuf:nullptr,cx,cy,_cursorWidth,_cursorHeight,_cursorKeyColor,cp);
}
'''+s[z:]
p.write_text(s)
# Check exact output-to-source row boundaries for all supported heights.
for h in range(1,241):
    edge=[(y*480+h-1)//h for y in range(h+1)]
    assert edge[0]==0 and edge[-1]==480
    assert all(y*h//480==sy for sy in range(h) for y in range(edge[sy],edge[sy+1]))
print("SC008: verified all fullscreen Y maps, fused palette and dirty source rows")

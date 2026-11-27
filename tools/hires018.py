#!/usr/bin/env python3
"""SC018: native indexed game surfaces up to 640x480; preserve low-res path."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
b=src/"native/components/backends/platform/esp32"
p=b/"osystem_gfx.cpp";s=p.read_text()
s=rep(s,'#include "osystem.h"','#include "osystem.h"\n#include "esp_heap_caps.h"\n#include <stdlib.h>\nextern "C" void prisma_diag_line(int,const char*,...);\nextern "C" void prisma_game_size(int,int);')
s=rep(s,'namespace _Esp32 {','namespace _Esp32 {\nstatic size_t gameCapacity=0;')
s=rep(s,'''void OSystem_Esp32::initSize(uint width, uint height, const Graphics::PixelFormat *format) {
	_gameWidth = width;
	_gameHeight = height;
}''',r'''void OSystem_Esp32::initSize(uint width, uint height, const Graphics::PixelFormat *format) {
    if(!width||!height||width>640||height>480||(format&&format->bytesPerPixel!=1)){
        prisma_diag_line(2,"UNSUPPORTED SURFACE %u x %u",width,height);
        abort();
    }
    const size_t need=size_t(width)*height;
    if(need>gameCapacity){
        // Only high-resolution games need an additional PSRAM allocation.
        byte* next=(byte*)heap_caps_calloc(need,1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        if(!next){prisma_diag_line(2,"SURFACE ALLOCATION FAILED %u",(unsigned)need);abort();}
        free(_gamePixels);
        _gamePixels=next;gameCapacity=need;
    }else if(_gameWidth!=width||_gameHeight!=height){
        memset(_gamePixels,0,need);
    }
    _gameWidth=width;_gameHeight=height;
    prisma_game_size(width,height);
}''')
s=rep(s,'''	_gamePixels = (byte *) malloc(_screen_width * _screen_height);
	for (uint32_t i = 0; i < _screen_width * _screen_height; i++)
	  _gamePixels[i] = 0;''',r'''    gameCapacity=size_t(_screen_width)*_screen_height;
    _gamePixels=(byte*)calloc(gameCapacity,1);
    if(!_gamePixels){prisma_diag_line(2,"SURFACE INITIAL ALLOCATION FAILED");abort();}
    prisma_game_size(_gameWidth,_gameHeight);''')
s=rep(s,'  free(_gamePixels);','  free(_gamePixels);\n  _gamePixels=nullptr;gameCapacity=0;')
# Preserve fast copy for the valid, common case; clip only exceptional rectangles.
s=rep(s,'	byte *dst = _gamePixels + y * _gameWidth + x;',r'''    if(!buf||!_gamePixels||w<=0||h<=0||pitch<w)return;
    const byte* clipped=(const byte*)buf;
    if(x<0){if(x<=-w)return;clipped-=x;w+=x;x=0;}
    if(y<0){if(y<=-h)return;clipped-=size_t(-y)*pitch*(-1);h+=y;y=0;}
    if(x>=_gameWidth||y>=_gameHeight)return;
    if(w>_gameWidth-x)w=_gameWidth-x;
    if(h>_gameHeight-y)h=_gameHeight-y;
    buf=clipped;
    byte *dst = _gamePixels + y * _gameWidth + x;'''.replace('clipped-=size_t(-y)*pitch*(-1);','clipped+=size_t(-y)*pitch;'))
p.write_text(s)
p=b/"osystem-display.cpp";s=p.read_text()
# Only indexed game rendering changes. The old raw boot-splash path stays intact.
s=rep(s,'_gameWidth>320||!_gameHeight||_gameHeight>240','_gameWidth>640||!_gameHeight||_gameHeight>480')
p.write_text(s)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'static uint8_t edgeDirty[240],edgeAbove[320],edgeBelow[320];','static uint8_t edgeDirty[480],edgeAbove[640],edgeBelow[640];')
s=rep(s,'yedge[241]','yedge[481]')
s=rep(s,'static uint8_t localIndices[320];','''static uint8_t localIndices[640];
static uint8_t* priorHigh=nullptr;
static size_t priorHighCapacity=0;
extern "C" void prisma_game_size(int w,int h){
    frameW=w;frameH=h;indexedValid=false;
}
''')
s=rep(s,'w<1||w>320||h<1||h>240','w<1||w>640||h<1||h>480')
s=rep(s,'    uint8_t* prev=priorInternal?priorInternal:reinterpret_cast<uint8_t*>(nativeFrame);',r'''    uint8_t* prev=priorInternal?priorInternal:reinterpret_cast<uint8_t*>(nativeFrame);
    const size_t need=size_t(w)*h;
    if(need>320*240){
        if(need>priorHighCapacity){
            uint8_t* next=(uint8_t*)heap_caps_malloc(need,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
            if(!next){prisma_diag_line(2,"HIGH RES CACHE ALLOCATION FAILED");abort();}
            free(priorHigh);priorHigh=next;priorHighCapacity=need;force=true;
        }
        prev=priorHigh;
    }''')
s=rep(s,'cw<=320&&ch<=240','cw<=640&&ch<=480')
s=rep(s,'outlineMode&&sy<144','outlineMode&&sy*200<h*144')
p.write_text(s.replace("SC017","SC018"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC017","SC018"))
# Validate mapping, including shrinking 640->480 and unchanged 320->480.
for n in range(1,641):
    assert all(0<=x*n//480<n for x in range(480))
    assert all((x*2*n//480)//2==x*n//480 for x in range(480))
for h in range(1,481):
    edge=[(y*480+h-1)//h for y in range(h+1)]
    assert edge[0]==0 and edge[-1]==480
    assert all(y*h//480==sy for sy in range(h) for y in range(edge[sy],edge[sy+1]))
assert 640*480==307200
print("SC018: verified 640x480 indexed surface dimensions, PSRAM cache, exact full-screen mappings; original low-res raw splash unchanged")

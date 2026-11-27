#!/usr/bin/env python3
"""SC005: preserve SC004 engine and game data. Restore original selector + renderer."""
from pathlib import Path
import sys, subprocess
root=Path(sys.argv[1]).resolve()
src=root/"src"
# Exact validated 071 scaler, independent of the emulated CPU.
original=subprocess.check_output(["git","-C",str(root),"show","HEAD:firmware/s3-4848-retro/src/game_video.h"])
(src/"game_video.h").write_bytes(original)
def replace(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp"
s=p.read_text()
s=replace(s,'#include "menu_canvas.h"','#include "menu_canvas.h"\n#include "game_video.h"')
s=replace(s,'extern "C" int prisma_scumm_run();','''extern "C" int prisma_scumm_run();
static uint8_t layoutMode=GameVideo::FIT;
static const char* layouts[]={"FULL","FIT","NATIVE"};
static uint16_t* nativeFrame=nullptr;
static int frameW=320,frameH=200;
static bool frameValid=false;
extern "C" void prisma_frame_begin(int w,int h){
    frameValid=nativeFrame&&w>0&&w<=320&&h>0&&h<=240;
    if(frameValid){frameW=w;frameH=h;}
}
''')
s=replace(s,'''    lcd.draw16bitRGBBitmap(x,y,const_cast<uint16_t*>(row),w,1);''','''    const int sy=y-(480-frameH)/2;
    if(frameValid&&row&&w==frameW&&x==(480-frameW)/2&&sy>=0&&sy<frameH)
        memcpy(nativeFrame+sy*frameW,row,w*2);''')
s=replace(s,'extern "C" void prisma_lcd_flush(){lcd.flush(true);}', '''extern "C" void prisma_lcd_flush(){
    if(frameValid)GameVideo::draw(lcd,nullptr,nullptr,nativeFrame,frameW,frameH,frameW,{layoutMode,false});
}''')
s=replace(s,'if(*down){*x=points[0].x;*y=points[0].y;}','''if(*down){
        int x0,y0,w,h;GameVideo::geometry(frameW,frameH,layoutMode,x0,y0,w,h);
        const int px=points[0].x,py=points[0].y;
        if(px<x0||py<y0||px>=x0+w||py>=y0+h){*x=-1;*y=-1;}
        else{*x=(480-frameW)/2+(px-x0)*frameW/w;*y=(480-frameH)/2+(py-y0)*frameH/h;}
    }''')
s=replace(s,'static volatile bool runtimeActive=false;','''static volatile bool runtimeActive=false;
// Adapt the 071 DOS carousel; preserve its geometry and navigation.
static void drawScummCarousel(){
    selected=true;
    auto& d=ui();const auto& t=RetroUI::themes[0];
    d.fillScreen(BG);
    RetroUI::button(d,12,10,90,44,"HOME",t);
    RetroUI::text(d,114,10,"PRISMA DOS",3,0xffff);
    RetroUI::text(d,114,39,"1 JUEGO / FLASH INTERNA",1,0x9cfa);
    d.fillRoundRect(56,70,368,344,8,0x2124);
    d.drawRoundRect(56,70,368,344,8,0x5e9e);
    RetroUI::console(d,138,122,6,0);
    RetroUI::center(d,240,352,"MONKEY ISLAND",2,0xffff);
    RetroUI::center(d,240,382,"VGA / 256 COLORES",1,0x9cfa);
    RetroUI::button(d,6,184,44,84,"<",t);
    RetroUI::button(d,430,184,44,84,">",t);
    RetroUI::button(d,12,436,150,32,layouts[layoutMode],t);
    RetroUI::button(d,318,436,150,32,"JUGAR",t,true);
    RetroUI::center(d,240,444,"1/1",2,0x9cfa);
    showUI();
}
''')
# Only one display owner after handoff; allocate pixel buffer in PSRAM before launching.
s=replace(s,'    runtimeActive=true;','''    if(!nativeFrame)nativeFrame=(uint16_t*)heap_caps_malloc(320*240*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!nativeFrame){Serial.println("SC005 FRAME ALLOCATION FAILED");drawScummCarousel();return false;}
    GameVideo::reset();
    Serial.printf("SC005 LAYOUT %s\\n",layouts[layoutMode]);
    runtimeActive=true;''')
s=replace(s,'runtimeActive=false;Serial.println("SC004 TASK ALLOCATION FAILED");homeUI();return false;','runtimeActive=false;free(nativeFrame);nativeFrame=nullptr;Serial.println("SC005 TASK ALLOCATION FAILED");drawScummCarousel();return false;')
s=replace(s,'''if(!selected&&hit(p,16,90,448,148)){menuCanvas.release();selected=dos_start(lcd);}
      else if(selected&&hit(p,12,10,90,44))homeUI();''','''if(!selected&&hit(p,16,90,448,148)){drawScummCarousel();}
      else if(selected&&hit(p,12,10,90,44))homeUI();
      else if(selected&&hit(p,12,436,150,32)){layoutMode=(layoutMode+1)%3;drawScummCarousel();}
      else if(selected&&(hit(p,56,70,368,344)||hit(p,318,436,150,32))){
          menuCanvas.release();dos_start(lcd);
      }''')
# Preserve old splash/menu; only label the new build.
s=s.replace("SC004","SC005")
p.write_text(s)
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC004","SC005"))
p=src/"native/components/backends/platform/esp32/osystem-display.cpp"
s=p.read_text()
s=replace(s,'extern "C" void prisma_lcd_flush();','extern "C" void prisma_lcd_flush();\nextern "C" void prisma_frame_begin(int,int);')
# Both raw splash and game drawing paths prepare a complete frame.
s=replace(s,'int left=(480-w)/2,top=(480-h)/2;','prisma_frame_begin(w,h);\n    int left=(480-w)/2,top=(480-h)/2;')
s=replace(s,'const int w=_gameWidth,h=_gameHeight,left=(480-w)/2,top=(480-h)/2;','const int w=_gameWidth,h=_gameHeight,left=(480-w)/2,top=(480-h)/2;\n    prisma_frame_begin(w,h);')
p.write_text(s)
print("SC005: original scaler, single-game carousel, inverse touch mapping; native engine unchanged")

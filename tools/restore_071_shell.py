#!/usr/bin/env python3
"""Restore the verified 071 Arduino shell; no emulator linked in this checkpoint."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
src=root/"src"
old=(src/"main.cpp").read_text()
def section(a,b):
    start=old.index(a)
    return old[start:old.index(b,start)]
# Exact board definitions, menu framebuffer and full-screen flush from 071.
board=section("static Arduino_SWSPI","static void showUIRects")
# Exact GT911 polling, including stale sample timeout.
touch=section("struct Point{","#ifdef PRISMA_COMBINED\nstruct DosTouchSample")
setup=section("  pinMode(38,OUTPUT);","  Serial.printf(\"LCD worker")
wire=section("  Wire1.begin(19,45,400000);","  Serial.println(\"BOOT 031 private ROM init")
main=r'''#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <Wire.h>
#include "retro_ui.h"
#include "menu_canvas.h"
'''
main+=board+"static uint8_t addr=0;\n"+touch+r'''
static const uint16_t BG=0x0842;
static bool splashVisible=true,splashPressed=false,wasDown=false,selected=false;
static bool hit(Point p,int x,int y,int w,int h){return p.x>=x&&p.x<x+w&&p.y>=y&&p.y<y+h;}
static void homeUI(){
  selected=false;
  unsigned counts[2]={1,0};
  RetroUI::home(ui(),counts);showUI();
}
// Runtime boundary from 071. The next change replaces only this function
// with native ScummVM on the same initialized LCD, not a second LCD owner.
bool dos_start(Arduino_RGB_Display& display){
  Serial.println("SC003 DOS HANDOFF reached; native engine not linked in this diagnostic");
  display.fillScreen(BG);
  RetroUI::center(display,240,180,"SCUMMVM",4,0xffff);
  RetroUI::center(display,240,236,"HANDOFF OK",3,0x07e0);
  RetroUI::center(display,240,294,"MONKEY ISLAND",2,0xffff);
  RetroUI::center(display,240,328,"MOTOR PENDIENTE",2,0x94b2);
  RetroUI::button(display,12,10,90,44,"HOME",RetroUI::themes[0]);
  display.flush(true);return true;
}
void setup(){
  Serial.begin(115200);delay(200);
  Serial.printf("SC003 RESET reason=%d CPU=%u flash=%u PSRAM=%u\n",(int)esp_reset_reason(),getCpuFrequencyMhz(),(unsigned)ESP.getFlashChipSize(),(unsigned)ESP.getPsramSize());
  Serial.println("SC003 LCD begin");Serial.flush();
'''
main+=setup+wire+r'''
  Serial.println("SC003 splash begin");
  RetroUI::splash(ui());showUI();
  Serial.println("SC003 splash ready / waiting touch");Serial.flush();
}
void loop(){
  if(!addr){delay(100);return;}
  pollTouch();
  if(splashVisible){
    if(npoints)splashPressed=true;
    else if(splashPressed){splashVisible=false;wasDown=false;Serial.println("SC003 home begin");homeUI();Serial.println("SC003 home ok");}
    delay(12);return;
  }
  if(npoints){if(!wasDown)gestureStart=points[0];gestureEnd=points[0];}
  if(!npoints&&wasDown){
    Point p=gestureStart;int dy=(int)gestureEnd.y-(int)p.y;int dx=(int)gestureEnd.x-(int)p.x;
    if(abs(dy)<36&&abs(dx)<36){
      if(!selected&&hit(p,16,90,448,148)){menuCanvas.release();selected=dos_start(lcd);}
      else if(selected&&hit(p,12,10,90,44))homeUI();
    }
  }
  wasDown=npoints>0;delay(12);
}
'''
# Remove all old game sources; retain original headers for shell only.
for p in src.iterdir():
    if p.name not in ("retro_ui.h","menu_canvas.h"):
        if p.is_file(): p.unlink()
(src/"main.cpp").write_text(main)
ui=src/"retro_ui.h"
s=ui.read_text()
assert s.count("for(int i=0;i<2;i++){const auto&t=themes[i];")==1
s=s.replace("for(int i=0;i<2;i++){const auto&t=themes[i];","for(int i=0;i<1;i++){const auto&t=themes[i];")
s=s.replace('"BUILD 071"','"BUILD SC003"').replace('text(d,403,19,"071",2','text(d,390,19,"SC003",2')
s=s.replace('"PC / x86"','"SCUMMVM / NATIVO"')
ui.write_text(s)
ini=root/"platformio.ini"
s=ini.read_text().split("[env:esp32-4848s040-dos]")[0]
s=s.replace("board_build.partitions = partitions.csv","board_build.partitions = partitions_scumm.csv")
s=s.replace(" -Ilib/nofrendo/src","").replace("-DARDUINO_USB_CDC_ON_BOOT=0","-DARDUINO_USB_CDC_ON_BOOT=0 -DPRISMA_COMBINED")
s="\n".join(l for l in s.splitlines() if not l.startswith("build_src_filter"))+"\n"
ini.write_text(s)
# Do not compile the previous emulator libraries.
import shutil
shutil.rmtree(root/"lib",ignore_errors=True)
(root/"partitions_scumm.csv").write_text("""# Name,Type,SubType,Offset,Size
nvs,data,nvs,0x9000,0x6000
phy_init,data,phy,0xf000,0x1000
factory,app,factory,0x10000,0x600000
games,data,fat,0x610000,0x9F0000
""")
print("SC003: 071 shell, exact LCD and GT911; engine handoff diagnostic only")

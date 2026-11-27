#!/usr/bin/env python3
"""SC007: fullscreen touch-only controls, no keyboard or changes to the engine."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
src=root/"src"
p=src/"native/components/backends/platform/esp32/osystem-events.cpp"
p.write_text(r'''#include "osystem.h"
namespace _Esp32 {
bool prismaTouch(int&,int&,bool&);
static int cursorX=160,cursorY=100;
static bool contact=false,dragged=false,rightHeld=false;
static int startX=0,startY=0;
static uint32_t started=0,lastSample=0;
static bool sampled=false;
static constexpr uint32_t HOLD_MS=500;
static constexpr uint32_t SAMPLE_MS=12;
static constexpr int MOVE_SLOP=8; // native pixels, roughly 12-19 screen pixels
uint16_t OSystem_Esp32::getCursorPosX(){return cursorX;}
uint16_t OSystem_Esp32::getCursorPosY(){return cursorY;}
void OSystem_Esp32::setCursorPosX(uint16_t x){cursorX=x;}
void OSystem_Esp32::setCursorPosY(uint16_t y){cursorY=y;}
void OSystem_Esp32::get_gamepad_state(esp_gamepad_state_t* s){*s={};}
void OSystem_Esp32::pushEventQueue(Common::Queue<Common::Event>* q,Common::Event& e){q->push(e);}
void OSystem_Esp32::report_keystate_to_engine(){}
void OSystem_Esp32::initEvents(){contact=dragged=rightHeld=sampled=false;}
void OSystem_Esp32::destroyEvents(){}
bool OSystem_Esp32::pollEvent(Common::Event& event){
    if(!_eventQueue.empty()){event=_eventQueue.pop();return true;}
    const uint32_t now=getMillis();
    // Do not flood the engine's while(pollEvent()) loop with identical motion.
    if(sampled && uint32_t(now-lastSample)<SAMPLE_MS)return false;
    sampled=true;lastSample=now;
    int x=0,y=0;bool down=false;
    if(!prismaTouch(x,y,down))return false;
    const int left=(480-_gameWidth)/2,top=(480-_gameHeight)/2;
    const bool inside=x>=left&&y>=top&&x<left+_gameWidth&&y<top+_gameHeight;
    auto send=[&](Common::EventType type){
        Common::Event e;
        e.type=type;e.mouse.x=cursorX;e.mouse.y=cursorY;
        _eventQueue.push(e);
    };
    if(down&&inside){
        const int nx=x-left,ny=y-top;
        if(!contact){
            contact=true;dragged=false;rightHeld=false;
            startX=nx;startY=ny;started=now;
        }
        if(nx!=cursorX||ny!=cursorY){
            cursorX=nx;cursorY=ny;
            send(Common::EVENT_MOUSEMOVE);
        }
        const int dx=nx-startX,dy=ny-startY;
        if(dx*dx+dy*dy>MOVE_SLOP*MOVE_SLOP)dragged=true;
        if(!dragged&&!rightHeld&&uint32_t(now-started)>=HOLD_MS){
            send(Common::EVENT_RBUTTONDOWN);rightHeld=true;
        }
    }else if(contact){
        if(rightHeld)send(Common::EVENT_RBUTTONUP);
        else if(!down&&!dragged){
            // Short tap: exactly one native left click. Two separate taps
            // remain two native clicks, with no synthetic Escape or speed hack.
            if(uint32_t(now-started)>=HOLD_MS){
                send(Common::EVENT_RBUTTONDOWN);send(Common::EVENT_RBUTTONUP);
            }else{
                send(Common::EVENT_LBUTTONDOWN);send(Common::EVENT_LBUTTONUP);
            }
        }
        contact=dragged=rightHeld=false;
    }
    if(_eventQueue.empty())return false;
    event=_eventQueue.pop();return true;
}
}
''')
# UI/boot version only, no alteration of screen geometry or menu.
for p in [src/"main.cpp",src/"retro_ui.h"]:
    p.write_text(p.read_text().replace("SC006","SC007"))
print("SC007: 500ms right hold, short tap on release, 12ms sampling, stationary event suppression")

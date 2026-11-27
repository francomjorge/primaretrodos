#!/usr/bin/env python3
"""SC009: multi-touch native shortcuts and measured engine timing."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'extern "C" bool prisma_touch_sample(int* x,int* y,bool* down){','extern "C" int prisma_touch_sample(int* x,int* y,bool* down){')
a=s.index('extern "C" int prisma_touch_sample');z=s.index('static volatile bool runtimeActive',a)
section=s[a:z]
section=rep(section,'return true;','return npoints;')
s=s[:a]+section+s[z:]
p.write_text(s.replace("SC008","SC009"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC008","SC009"))
b=src/"native/components/backends/platform/esp32"
p=b/"osystem-input.cpp";s=p.read_text()
s=rep(s,'extern "C" bool prisma_touch_sample(int*,int*,bool*);','extern "C" int prisma_touch_sample(int*,int*,bool*);')
s=rep(s,'bool prismaTouch(int& x,int& y,bool& down)','int prismaTouch(int& x,int& y,bool& down)')
p.write_text(s)
p=b/"osystem-events.cpp";s=p.read_text()
s=rep(s,'bool prismaTouch(int&,int&,bool&);','int prismaTouch(int&,int&,bool&);')
s=rep(s,'static bool sampled=false;','static bool sampled=false;\nstatic unsigned multiPeak=0;')
s=rep(s,'contact=dragged=rightHeld=sampled=false;','contact=dragged=rightHeld=sampled=false;multiPeak=0;')
s=rep(s,'    if(!prismaTouch(x,y,down))return false;','    const int count=prismaTouch(x,y,down);')
s=rep(s,'    if(down&&inside){','''    // Resolve on all-fingers-up, so a staggered three-finger press
    // never emits Escape first. No mouse click leaks out of the chord.
    if(count>=2){
        if(rightHeld)send(Common::EVENT_RBUTTONUP);
        contact=dragged=rightHeld=false;
        if(unsigned(count)>multiPeak)multiPeak=count;
    }else if(multiPeak){
        if(count==0){
            const unsigned peak=multiPeak;multiPeak=0;
            if(peak==2||peak==3){
                Common::Event k;
                k.kbd=Common::KeyState(peak==3?Common::KEYCODE_F5:Common::KEYCODE_ESCAPE,
                                      peak==3?319:27);
                k.type=Common::EVENT_KEYDOWN;_eventQueue.push(k);
                k.type=Common::EVENT_KEYUP;_eventQueue.push(k);
                printf("SC009 GESTURE %s\\n",peak==3?"F5":"ESC");
            }
        }
    }else if(down&&inside){''')
p.write_text(s)
# The upstream menu constructor is commented out; guard the known null pointer.
# Do not claim a functioning save dialog while the backend GUI is unimplemented.
p=src/"native/components/engines/engine.cpp";s=p.read_text()
s=rep(s,'void Engine::openMainMenuDialog() {','''void Engine::openMainMenuDialog() {
    if(!_mainMenuDialog){
        printf("SC009 F5 received: native menu unavailable in upstream port\\n");
        return;
    }''')
p.write_text(s)
# Keep original script delta and real clock. Eliminate oversleep at the end
# of timer windows and measure time spent in the game loop versus waiting.
p=src/"native/components/scumm/scumm.cpp";s=p.read_text()
s=rep(s,'\t\twaitForTimer(delta * 1000 / 60 - diff);','''        const uint32 waitStart=_system->getMillis();
        const int budget=delta*1000/60;
        const int remaining=budget-int(diff);
        waitForTimer(remaining>0?remaining:0);
        static uint32 profStart=0,profLoops=0,profLogic=0,profWait=0,profLate=0;
        const uint32 afterWait=_system->getMillis();
        if(!profStart)profStart=waitStart;
        profWait+=afterWait-waitStart;
        if(remaining<0)++profLate;''')
s=rep(s,'\t\tdiff = _system->getMillis() - diff;','''        diff = _system->getMillis() - diff;
        profLogic+=diff;++profLoops;
        const uint32 profNow=_system->getMillis();
        if(profNow-profStart>=3000){
            printf("SC009 CPU ms=%u loops=%u logic_ms=%u wait_ms=%u late=%u\\\\n",
                (unsigned)(profNow-profStart),(unsigned)profLoops,(unsigned)profLogic,
                (unsigned)profWait,(unsigned)profLate);
            profStart=profNow;profLoops=profLogic=profWait=profLate=0;
        }''')
s=rep(s,'\t\tif (_system->getMillis() >= start_time + msec_delay)\n\t\t\tbreak;\n\t\t_system->delayMillis(10);','''        const uint32 elapsed=_system->getMillis()-start_time;
        if(msec_delay<=0||elapsed>=uint32(msec_delay))break;
        const uint32 left=uint32(msec_delay)-elapsed;
        _system->delayMillis(left<10?left:10);''')
s=s.replace('late=%u\\\\n','late=%u\\n')
p.write_text(s)
p=b/"osystem.cpp";s=p.read_text()
s=rep(s,'vTaskDelay( msecs / portTICK_PERIOD_MS );','''const TickType_t ticks=(msecs+portTICK_PERIOD_MS-1)/portTICK_PERIOD_MS;
        if(ticks)vTaskDelay(ticks);else taskYIELD();''')
p.write_text(s)
print("SC009: two-finger Escape, three-finger F5, safe disabled menu, bounded timer wait and CPU diagnostics")

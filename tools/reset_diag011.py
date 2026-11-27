#!/usr/bin/env python3
"""SC011 diagnostic-only branch from physically tested SC009."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'#include "game_video.h"','#include "game_video.h"\n#include <esp_attr.h>\n#include <stdarg.h>')
a=s.index('extern "C" int prisma_scumm_run();')
s=s[:a]+r'''
// Compact retained record, independent of USB reconnects. Only the game task
// writes after handoff; setup and the idle menu use it before handoff.
struct ScDiag {
    uint32_t magic,phase,seq;
    char gfx[192],cpu[192],event[96];
};
RTC_NOINIT_ATTR static ScDiag diag;
static uint32_t bootReset=0,previousPhase=0;
static bool unexpectedReset=false;
static bool diagLive=false;
extern "C" void prisma_diag_phase(uint32_t phase){diag.phase=phase;}
extern "C" void prisma_diag_line(int kind,const char* fmt,...){
    char buf[192];va_list ap;va_start(ap,fmt);vsnprintf(buf,sizeof(buf),fmt,ap);va_end(ap);
    char* dst=kind==0?diag.gfx:kind==1?diag.cpu:diag.event;
    const size_t n=kind==2?sizeof(diag.event):sizeof(diag.gfx);
    snprintf(dst,n,"%s",buf);++diag.seq;
    if(diagLive||kind==2)Serial.println(dst);
}
static void scDiagDump(){
    Serial.println("SC011 LOG BEGIN");
    Serial.printf("RESET=%u PREVIOUS_PHASE=%u PHASE=%u SEQ=%u\n",
        (unsigned)bootReset,(unsigned)previousPhase,(unsigned)diag.phase,(unsigned)diag.seq);
    if(diag.gfx[0])Serial.println(diag.gfx);
    if(diag.cpu[0])Serial.println(diag.cpu);
    if(diag.event[0])Serial.println(diag.event);
    Serial.printf("HEAP=%u PSRAM=%u STACK=%u\n",(unsigned)ESP.getFreeHeap(),
        (unsigned)ESP.getFreePsram(),(unsigned)uxTaskGetStackHighWaterMark(nullptr));
    Serial.println("SC011 LOG END");
}
static void scDiagInit(){
    bootReset=esp_reset_reason();
    if(diag.magic!=0x53434431u||bootReset==ESP_RST_POWERON||bootReset==ESP_RST_BROWNOUT){
        memset(&diag,0,sizeof(diag));diag.magic=0x53434431u;
    }
    previousPhase=diag.phase;
    diag.phase=1;
    unexpectedReset=bootReset==ESP_RST_PANIC||bootReset==ESP_RST_INT_WDT||
        bootReset==ESP_RST_TASK_WDT||bootReset==ESP_RST_WDT||bootReset==ESP_RST_BROWNOUT;
    scDiagDump();
}
extern "C" void prisma_diag_poll(){
    static char line[32];static unsigned used=0;
    // Commands only; never forward to the game as keyboard input.
    for(int i=0;i<16&&Serial.available();i++){
        const int c=Serial.read();
        if(c=='\r'||c=='\n'){
            if(!used)continue;
            line[used]=0;
            if(!strcmp(line,":log")||!strcmp(line,":status"))scDiagDump();
            else if(!strcmp(line,":live")){diagLive=true;Serial.println("SC011 LIVE ON");}
            else if(!strcmp(line,":quiet")){diagLive=false;Serial.println("SC011 LIVE OFF");}
            used=0;
        }else if(c>=32&&c<127&&used<sizeof(line)-1)line[used++]=char(c);
    }
}
'''+s[a:]
s=rep(s,'Serial.begin(115200);delay(200);','Serial.begin(115200);delay(200);scDiagInit();')
s=rep(s,'void loop(){\n  if(runtimeActive){delay(20);return;}','void loop(){\n  if(runtimeActive){delay(20);return;}\n  prisma_diag_poll();')
s=rep(s,'    int rc=prisma_scumm_run();','    prisma_diag_phase(2);\n    int rc=prisma_scumm_run();')
s=rep(s,'    if(!nativeFrame||!pixels||!palette||!cursorPalette||w<1||w>320||h<1||h>240)return;','    if(!nativeFrame||!pixels||!palette||!cursorPalette||w<1||w>320||h<1||h>240)return;\n    prisma_diag_phase(4);')
s=rep(s,'    if(written){lcd.flush(true);renderPresents++;}','    if(written){prisma_diag_phase(5);lcd.flush(true);renderPresents++;}')
s=rep(s,'        Serial.printf("SC009 PERF ms=%u requests=%u presents=%u avg_us=%u flush_avg_us=%u dirty_rows=%u lcd_pixels=%u heap=%u psram=%u\\n",','        prisma_diag_line(0,"GFX ms=%u req=%u fps_frames=%u us=%u flush_us=%u rows=%u px=%u heap=%u psram=%u",')
s=rep(s,'    RetroUI::center(d,240,444,"1/1",2,0x9cfa);','''    RetroUI::center(d,240,444,"1/1",2,0x9cfa);
    if(unexpectedReset){
        char r[32];snprintf(r,sizeof(r),"RESET %u P%u",(unsigned)bootReset,(unsigned)previousPhase);
        RetroUI::text(d,12,450,r,1,0xfbe0);
    }''')
p.write_text(s.replace("SC009","SC011"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC009","SC011"))
b=src/"native/components/backends/platform/esp32"
p=b/"osystem-events.cpp";s=p.read_text()
s=rep(s,'#include "osystem.h"','#include "osystem.h"\nextern "C" void prisma_diag_poll();\nextern "C" void prisma_diag_line(int,const char*,...);')
s=rep(s,'    sampled=true;lastSample=now;','    sampled=true;lastSample=now;\n    prisma_diag_poll();')
s=rep(s,'                printf("SC009 GESTURE %s\\n",peak==3?"F5":"ESC");','                prisma_diag_line(2,"GESTURE %s fingers=%u",peak==3?"F5":"ESC",peak);')
p.write_text(s)
p=src/"native/components/scumm/scumm.cpp";s=p.read_text()
# Put declarations outside the namespace, before the existing includes.
s='extern "C" void prisma_diag_phase(unsigned int);\nextern "C" void prisma_diag_line(int,const char*,...);\n'+s
s=rep(s,'\t\tscummLoop(delta);','        prisma_diag_phase(3);\n\t\tscummLoop(delta);')
s=rep(s,'            printf("SC009 CPU ms=%u loops=%u logic_ms=%u wait_ms=%u late=%u\\n",','            prisma_diag_line(1,"CPU ms=%u loops=%u logic=%u wait=%u late=%u",')
p.write_text(s)
print("SC011: retained diagnostic snapshots, serial quiet by default, reset reason on game selector; no new performance changes")

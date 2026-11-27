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
    char gfx[192],cpu[192],event[96],profile[192];
};
RTC_NOINIT_ATTR static ScDiag diag;
static uint32_t bootReset=0,previousPhase=0;
static bool unexpectedReset=false;
static bool diagLive=false;

struct TestCapture {
    bool active;
    uint32_t start;
    char name[16];
    unsigned seen[4], samples[4];
    uint64_t gfx[7],cpu[5],profile[8];
    unsigned gestures;
};
static TestCapture capture={};
static char lastSummary[800]={};
static void scTestStart(const char* name){
    const char* valid[]={"idle","walk","scroll","actors","both","touch"};
    bool ok=false;for(auto v:valid)if(!strcmp(v,name))ok=true;
    if(!ok){Serial.println("TEST: idle walk scroll actors both touch");return;}
    if(capture.active){Serial.println("TEST ACTIVE; use :end");return;}
    memset(&capture,0,sizeof(capture));capture.active=true;capture.start=millis();
    snprintf(capture.name,sizeof(capture.name),"%s",name);
    diagLive=false;
    Serial.printf("TEST %s BEGIN 20s; perform action now\n",capture.name);
}
static void scTestRecord(int kind,const char* line){
    if(!capture.active||kind<0||kind>3)return;
    if(kind==2){capture.gestures++;return;}
    // Discard first interval of each independent 3s producer: it may
    // include time preceding the requested scenario.
    if(capture.seen[kind]++==0)return;
    unsigned v[9]={};int n=0;
    if(kind==0){
        n=sscanf(line,"GFX ms=%u req=%u fps_frames=%u us=%u flush_us=%u rows=%u px=%u heap=%u psram=%u",&v[0],&v[1],&v[2],&v[3],&v[4],&v[5],&v[6],&v[7],&v[8]);
        if(n!=9)return;
        capture.gfx[0]+=v[0];capture.gfx[1]+=v[1];capture.gfx[2]+=v[2];
        capture.gfx[3]+=uint64_t(v[3])*v[1];capture.gfx[4]+=uint64_t(v[4])*v[2];capture.gfx[5]+=v[5];capture.gfx[6]+=v[6];
    }else if(kind==1){
        n=sscanf(line,"CPU ms=%u loops=%u logic=%u wait=%u late=%u",&v[0],&v[1],&v[2],&v[3],&v[4]);
        if(n!=5)return;for(int i=0;i<5;i++)capture.cpu[i]+=v[i];
    }else{
        n=sscanf(line,"PHASE ms=%u loops=%u scrolling=%u scripts_ms=%u walk_camera_ms=%u bg_ms=%u actors_ms=%u copy_ms=%u",&v[0],&v[1],&v[2],&v[3],&v[4],&v[5],&v[6],&v[7]);
        if(n!=8)return;for(int i=0;i<8;i++)capture.profile[i]+=v[i];
    }
    capture.samples[kind]++;
}
static double rate(uint64_t n,uint64_t d){return d?double(n)/double(d):0.0;}
static void scTestEnd(){
    if(!capture.active){Serial.println("NO ACTIVE TEST");return;}
    capture.active=false;
    auto& g=capture.gfx;auto& c=capture.cpu;auto& p=capture.profile;
    snprintf(lastSummary,sizeof(lastSummary),
        "TEST %s END duration_ms=%u\n"
        "GFX samples=%u ms=%llu fps=%.2f render_us=%.0f flush_us=%.0f rows=%llu pixels=%llu\n"
        "CPU samples=%u ms=%llu loops_s=%.2f logic_ms=%.2f wait_ms=%.2f late=%llu\n"
        "PHASE samples=%u ms=%llu scroll_loops=%llu script=%.2f camera=%.2f bg=%.2f actors=%.2f copy=%.2f ms/loop\n"
        "GESTURES=%u RESET=%u HEAP=%u PSRAM=%u",
        capture.name,(unsigned)(millis()-capture.start),
        capture.samples[0],(unsigned long long)g[0],rate(g[2]*1000,g[0]),rate(g[3],g[1]),rate(g[4],g[2]),(unsigned long long)g[5],(unsigned long long)g[6],
        capture.samples[1],(unsigned long long)c[0],rate(c[1]*1000,c[0]),rate(c[2],c[1]),rate(c[3],c[1]),(unsigned long long)c[4],
        capture.samples[3],(unsigned long long)p[0],(unsigned long long)p[2],rate(p[3],p[1]),rate(p[4],p[1]),rate(p[5],p[1]),rate(p[6],p[1]),rate(p[7],p[1]),
        capture.gestures,(unsigned)bootReset,(unsigned)ESP.getFreeHeap(),(unsigned)ESP.getFreePsram());
    Serial.println(lastSummary);
}

extern "C" void prisma_diag_phase(uint32_t phase){diag.phase=phase;}
extern "C" void prisma_diag_line(int kind,const char* fmt,...){
    char buf[192];va_list ap;va_start(ap,fmt);vsnprintf(buf,sizeof(buf),fmt,ap);va_end(ap);
    char* dst=kind==0?diag.gfx:kind==1?diag.cpu:kind==3?diag.profile:diag.event;
    const size_t n=kind==2?sizeof(diag.event):sizeof(diag.gfx);
    snprintf(dst,n,"%s",buf);++diag.seq;
    scTestRecord(kind,buf);
    if(diagLive&&!capture.active)Serial.println(dst);
}
static void scDiagDump(){
    Serial.println("SC011 LOG BEGIN");
    Serial.printf("RESET=%u PREVIOUS_PHASE=%u PHASE=%u SEQ=%u\n",
        (unsigned)bootReset,(unsigned)previousPhase,(unsigned)diag.phase,(unsigned)diag.seq);
    if(diag.gfx[0])Serial.println(diag.gfx);
    if(diag.cpu[0])Serial.println(diag.cpu);
    if(diag.event[0])Serial.println(diag.event);
    if(diag.profile[0])Serial.println(diag.profile);
    Serial.printf("HEAP=%u PSRAM=%u STACK=%u\n",(unsigned)ESP.getFreeHeap(),
        (unsigned)ESP.getFreePsram(),(unsigned)uxTaskGetStackHighWaterMark(nullptr));
    Serial.println("SC011 LOG END");
}
static void scDiagInit(){
    bootReset=esp_reset_reason();
    if(diag.magic!=0x53434432u||bootReset==ESP_RST_POWERON||bootReset==ESP_RST_BROWNOUT){
        memset(&diag,0,sizeof(diag));diag.magic=0x53434432u;
    }
    previousPhase=diag.phase;
    diag.phase=1;
    unexpectedReset=bootReset==ESP_RST_PANIC||bootReset==ESP_RST_INT_WDT||
        bootReset==ESP_RST_TASK_WDT||bootReset==ESP_RST_WDT||bootReset==ESP_RST_BROWNOUT;
    scDiagDump();
}
extern "C" void prisma_diag_poll(){
    static char line[32];static unsigned used=0;
    if(capture.active&&millis()-capture.start>=20000)scTestEnd();
    // Commands only; never forward to the game as keyboard input.
    for(int i=0;i<16&&Serial.available();i++){
        const int c=Serial.read();
        if(c=='\r'||c=='\n'){
            if(!used)continue;
            line[used]=0;
            if(!strncmp(line,":test ",6))scTestStart(line+6);
            else if(!strcmp(line,":end"))scTestEnd();
            else if(!strcmp(line,":result")){if(lastSummary[0])Serial.println(lastSummary);else Serial.println("NO RESULT");}
            else if(!strcmp(line,":log")||!strcmp(line,":status"))scDiagDump();
            else if(!strcmp(line,":live")&&!capture.active){diagLive=true;Serial.println("SC011 LIVE ON");}
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

# Remove repetitive per-frame messages; retain backend errors and warnings.
p=b/"osystem_gfx.cpp";s=p.read_text()
s=s.replace('printf("*OSystem_Esp32::lockScreen()\\n");','').replace('printf("OSystem_Esp32::unlockScreen()\\n");','')
p.write_text(s)
p=b/"osystem.cpp";s=p.read_text()
s=s.replace('void OSystem_Esp32::logMessage(LogMessageType::Type, const char* msg) {if(msg)printf("%s",msg);}','void OSystem_Esp32::logMessage(LogMessageType::Type type, const char* msg) {if(msg&&(type==LogMessageType::kError||type==LogMessageType::kWarning))printf("%s",msg);}')
p.write_text(s)

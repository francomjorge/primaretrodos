#!/usr/bin/env python3
"""SC012: no unsolicited runtime console output. Keep explicit test results."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/"src/main.cpp";s=p.read_text()
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
s=rep(s,'#include <stdarg.h>','#include <stdarg.h>\n#include <stdio.h>\n#include <esp_log.h>')
# Link-level wrappers mute native C console calls but never file output,
# snprintf/vsnprintf, or Arduino Serial.print/printf used by our commands.
anchor='// Compact retained record, independent of USB reconnects.'
s=rep(s,anchor,r'''
extern "C" int __real_vfprintf(FILE*,const char*,va_list);
extern "C" int __real_fputs(const char*,FILE*);
extern "C" int __real_fputc(int,FILE*);
static bool scConsole(FILE* f){return f==stdout||f==stderr;}
extern "C" int __wrap_printf(const char*,...){return 0;}
extern "C" int __wrap_vprintf(const char*,va_list){return 0;}
extern "C" int __wrap_puts(const char*){return 0;}
extern "C" int __wrap_putchar(int c){return c;}
extern "C" int __wrap_fprintf(FILE* f,const char* fmt,...){
    if(scConsole(f))return 0;
    va_list args;va_start(args,fmt);int r=__real_vfprintf(f,fmt,args);va_end(args);return r;
}
extern "C" int __wrap_vfprintf(FILE* f,const char* fmt,va_list args){
    return scConsole(f)?0:__real_vfprintf(f,fmt,args);
}
extern "C" int __wrap_fputs(const char* text,FILE* f){
    return scConsole(f)?0:__real_fputs(text,f);
}
extern "C" int __wrap_fputc(int c,FILE* f){
    return scConsole(f)?c:__real_fputc(c,f);
}
static int scQuietLog(const char*,va_list){return 0;}
'''+anchor)
s=rep(s,'Serial.begin(115200);delay(200);scDiagInit();','Serial.begin(115200);esp_log_set_vprintf(scQuietLog);esp_log_level_set("*",ESP_LOG_NONE);delay(200);scDiagInit();')
s=rep(s,'    scDiagDump();\n}\nextern "C" void prisma_diag_poll()', '}\nextern "C" void prisma_diag_poll()')
s=rep(s,'    if(diagLive&&!capture.active)Serial.println(dst);','    // Metrics are retained, not streamed.')
s=rep(s,'else if(!strcmp(line,":live")&&!capture.active){diagLive=true;Serial.println("SC012 LIVE ON");}','else if(!strcmp(line,":live")){Serial.println("STREAM DISABLED; use :test or :result");}')
s=rep(s,'else if(!strcmp(line,":quiet")){diagLive=false;Serial.println("SC012 LIVE OFF");}','else if(!strcmp(line,":quiet")){diagLive=false;}')
# The only late native Serial line in the dense renderer is initialization.
s=rep(s,'        Serial.printf("SC012 RENDER prior=%s\\n",priorInternal?"SRAM":"PSRAM");','')
p.write_text(s)
# Keep warnings available in the retained event record without printing.
p=root/"src/native/components/backends/platform/esp32/osystem.cpp";s=p.read_text()
old='void OSystem_Esp32::logMessage(LogMessageType::Type type, const char* msg) {if(msg&&(type==LogMessageType::kError||type==LogMessageType::kWarning))printf("%s",msg);}'
if old in s:
    s='extern "C" void prisma_diag_line(int,const char*,...);\n'+s.replace(old,'void OSystem_Esp32::logMessage(LogMessageType::Type type, const char* msg) {if(msg&&type==LogMessageType::kError)prisma_diag_line(2,"ERROR %.80s",msg);}')
    # Error events must not increment gesture totals.
    q=root/"src/main.cpp";t=q.read_text();t=t.replace('if(kind==2){capture.gestures++;return;}','if(kind==2){if(!strncmp(line,"GESTURE ",8))capture.gestures++;return;}');q.write_text(t)
p.write_text(s)
p=root/"platformio.ini";s=p.read_text()
flags=" ".join("-Wl,--wrap="+name for name in ("printf","vprintf","puts","putchar","fprintf","vfprintf","fputs","fputc"))
s=rep(s,"build_flags = ","build_flags = -DCORE_DEBUG_LEVEL=0 "+flags+" ")
p.write_text(s)
print("SC012: native console and ESP logging muted; only explicit Arduino diagnostic commands and critical startup/reset output remain")

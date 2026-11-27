#!/usr/bin/env python3
"""SC010: optimize dense scrolling, add engine phase and GT911 diagnostics."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
# Use internal SRAM for the previous indexed image when available.
# Existing PSRAM allocation remains the fallback and raw splash buffer.
s=rep(s,'static uint8_t localIndices[320];','''static uint8_t localIndices[320];
static uint8_t* priorInternal=nullptr;
static bool priorTried=false;''')
s=rep(s,'    uint8_t* prev=reinterpret_cast<uint8_t*>(nativeFrame);','''    if(!priorTried){
        priorTried=true;
        priorInternal=(uint8_t*)heap_caps_malloc(320*240,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
        if(priorInternal)force=true;
        Serial.printf("SC010 RENDER prior=%s\\\\n",priorInternal?"SRAM":"PSRAM");
    }
    uint8_t* prev=priorInternal?priorInternal:reinterpret_cast<uint8_t*>(nativeFrame);''')
s=rep(s,'        if(!force&&!cursorNow&&!cursorBefore&&!memcmp(previous,input,w))continue;','''        const bool sourceChanged=force||memcmp(previous,input,w)!=0;
        if(!sourceChanged&&!cursorNow&&!cursorBefore)continue;''')
a=s.index('        const int lo=cursorNow?');z=s.index('        const int y0=yedge[sy]',a)
s=s[:a]+'''        // Exact 320->480 nearest-neighbour: [a,a,b] for each pair.
        if(w==320){
            for(int sx=0,x=0;sx<320;sx+=2,x+=3){
                const uint16_t a=localPal[localIndices[sx]],b=localPal[localIndices[sx+1]];
                scaled[x]=a;scaled[x+1]=a;scaled[x+2]=b;
            }
        }else{
            for(int x=0;x<480;x++)scaled[x]=localPal[localIndices[xmapFull[x]]];
        }
        // Cursor composition only over its actual destination span.
        if(cursorNow){
            const int lo=max(0,cx),hi=min(w,cx+cw);
            const int x0=(lo*480+w-1)/w,x1=(hi*480+w-1)/w;
            for(int x=x0;x<x1;x++){
                const int sx=xmapFull[x];
                const uint8_t v=mouse[(sy-cy)*cw+sx-cx];
                if(v!=key)scaled[x]=localCursorPal[v];
            }
        }
'''+s[z:]
# Dirty indexed rows known to differ: skip costly PSRAM RGB readback.
# Preserve output comparison for cursor-only rows.
s=rep(s,'if(!force&&!memcmp(dst,scaled,sizeof(scaled)))continue;','if(!sourceChanged&&!memcmp(dst,scaled,sizeof(scaled)))continue;')
# Diagnostic at hardware touch source, including rejected coordinates and I2C errors.
a=s.index('static void pollTouch(){');z=s.index('extern "C" int prisma_touch_sample',a)
t=s[a:z]
t=rep(t,'  uint8_t st=0;','  static int lastRaw=-1,lastAccepted=-1;static unsigned errors=0;\\n  uint8_t st=0;'.replace('\\n','\n'))
t=rep(t,'if(!readReg(0x814E,&st,1)){npoints=0;return;}','if(!readReg(0x814E,&st,1)){if((++errors%32)==1)Serial.printf("SC010 TOUCH status_errors=%u\\\\n",errors);npoints=0;return;}')
t=rep(t,'  clearTouch();','''  if(count!=lastRaw||npoints!=lastAccepted){
      Serial.printf("SC010 TOUCH raw=%u valid=%u\\\\n",count,npoints);
      lastRaw=count;lastAccepted=npoints;
  }
  clearTouch();''')
s=s[:a]+t+s[z:]
s=s.replace("SC009","SC010").replace('\\\\n','\\n')
p.write_text(s)
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC009","SC010"))
# Phase measurements are accumulated per loop, not printed per frame.
p=src/"native/components/scumm/scumm.cpp";s=p.read_text()
a=s.index("void ScummEngine::scummLoop(int delta) {");z=s.index("#ifdef ENABLE_HE",a)
t=s[a:z]
t=rep(t,"void ScummEngine::scummLoop(int delta) {",'''void ScummEngine::scummLoop(int delta) {
    static uint32 profileAt=0,profileN=0,profileScripts=0,profileCamera=0,profileBg=0,profileActors=0,profileCopy=0,profileScroll=0;
    const uint32 profileBegin=_system->getMillis();
    uint32 phase=profileBegin;
    if(!profileAt)profileAt=profileBegin;''')
t=rep(t,"\trunAllScripts();\n\tcheckExecVerbs();\n\tcheckAndRunSentenceScript();","\trunAllScripts();\n\tcheckExecVerbs();\n\tcheckAndRunSentenceScript();\n    profileScripts+=_system->getMillis()-phase;")
t=rep(t,"\t\twalkActors();\n\t\tmoveCamera();","    phase=_system->getMillis();\n\t\twalkActors();\n\t\tmoveCamera();\n    profileCamera+=_system->getMillis()-phase;\n    if(camera._cur!=camera._last)++profileScroll;")
t=rep(t,"\t\tscummLoop_handleDrawing();\n\n\t\tscummLoop_handleActors();","    phase=_system->getMillis();\n\t\tscummLoop_handleDrawing();\n    profileBg+=_system->getMillis()-phase;phase=_system->getMillis();\n\t\tscummLoop_handleActors();\n    profileActors+=_system->getMillis()-phase;")
t=rep(t,"\t\tupdatePalette();\n\t\tdrawDirtyScreenParts();","    phase=_system->getMillis();\n\t\tupdatePalette();\n\t\tdrawDirtyScreenParts();\n    profileCopy+=_system->getMillis()-phase;")
t=rep(t,"\tCursorMan.showMouse(_cursor.state > 0);","""\tCursorMan.showMouse(_cursor.state > 0);
    ++profileN;
    const uint32 end=_system->getMillis();
    if(end-profileAt>=3000){
        printf("SC010 PHASE ms=%u loops=%u scrolling=%u scripts_ms=%u walk_camera_ms=%u bg_ms=%u actors_ms=%u copy_ms=%u\\\\n",
            (unsigned)(end-profileAt),(unsigned)profileN,(unsigned)profileScroll,(unsigned)profileScripts,
            (unsigned)profileCamera,(unsigned)profileBg,(unsigned)profileActors,(unsigned)profileCopy);
        profileAt=end;profileN=profileScripts=profileCamera=profileBg=profileActors=profileCopy=profileScroll=0;
    }""")
s=(s[:a]+t+s[z:]).replace("SC009","SC010").replace('\\\\n','\\n')
p.write_text(s)
p=src/"native/components/backends/platform/esp32/osystem-events.cpp"
s=p.read_text().replace("SC009","SC010")
p.write_text(s)
# Check optimized horizontal mapping matches original exactly.
assert [x*320//480 for x in range(480)]==[v for i in range(0,320,2) for v in (i,i,i+1)]
print("SC010: exact 3:2 scaler, dense row path, internal cache fallback, touch counts and engine phase profile")

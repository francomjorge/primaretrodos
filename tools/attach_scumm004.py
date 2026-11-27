#!/usr/bin/env python3
"""SC004: keep validated SC003 Arduino shell and link the pinned native engine."""
from pathlib import Path
import re,sys,shutil,subprocess
root=Path(sys.argv[1]).resolve()
up=Path(sys.argv[2]).resolve()
subprocess.run([sys.executable,str(Path(__file__).with_name("port_sc001.py")),str(up)],check=True)
b=up/"components/backends/platform/esp32"
def edit(p,f):
    s=p.read_text(); n=f(s); assert n!=s,p; p.write_text(n)
# Reuse display rendering from SC002, replace the entire LCD driver with C ABI
# to the existing Arduino_GFX instance. No second panel or pin initialization.
p=b/"osystem-display.cpp"
s=p.read_text()
start=s.index('#include "driver/gpio.h"')
end=s.index("namespace _Esp32 {",start)
s=s[:start]+'''#include "esp_timer.h"
#include "esp_heap_caps.h"
extern "C" void prisma_lcd_row(int,int,int,const uint16_t*);
extern "C" void prisma_lcd_flush();
'''+s[end:]
start=s.index("static void word9(")
end=s.index("void OSystem_Esp32::display_send_buf_raw",start)
s=s[:start]+'''static bool ready=false;
static uint16_t row[320];
void OSystem_Esp32::backlight_set(int){}
int OSystem_Esp32::is_backlight_initialized(){return ready;}
bool OSystem_Esp32::initDisplay(){
    ready=true; _screen_width=320; _screen_height=240;
    printf("SC004 LCD inherited from SC003\\n");fflush(stdout);return true;
}
void OSystem_Esp32::lcd_set_addr(uint16_t,uint16_t,uint16_t,uint16_t){}
void OSystem_Esp32::destroyDisplay(){}
'''+s[end:]
s=s.replace("lcd.pushImage(left,top+y,w,1,row);","prisma_lcd_row(left,top+y,w,row);")
s=s.replace("    }\n}\nvoid OSystem_Esp32::display_flush()", "    }\n    prisma_lcd_flush();\n}\nvoid OSystem_Esp32::display_flush()")
s=s.replace("    work+=esp_timer_get_time()-t;","    prisma_lcd_flush();\n    work+=esp_timer_get_time()-t;")
p.write_text(s)
# Keep GT911 exclusively under the validated Wire1 driver, with release reporting.
(b/"osystem-input.cpp").write_text('''#include "osystem.h"
extern "C" bool prisma_touch_sample(int*,int*,bool*);
namespace _Esp32 {
bool prismaTouch(int& x,int& y,bool& down){return prisma_touch_sample(&x,&y,&down);}
bool OSystem_Esp32::isInputInit(){return _isInputInit;}
esp_gamepad_state_t OSystem_Esp32::hw_input_read_raw(){return {};}
void OSystem_Esp32::initInput(){_isInputInit=true;printf("SC004 GT911 inherited\\n");}
}
''')
# Read-only FAT via IDF raw partition API (no wear-level layout dependency).
(b/"osystem-sdcard.cpp").write_text('''#include "osystem.h"
#include "esp_vfs_fat.h"
static bool mounted=false;
extern "C" bool prisma_mount_games(){
    if(mounted)return true;
    esp_vfs_fat_mount_config_t cfg={}; cfg.max_files=15;
    esp_err_t err=esp_vfs_fat_spiflash_mount_ro("/flash","games",&cfg);
    printf("SC004 FLASH FAT %s\\n",esp_err_to_name(err));fflush(stdout);
    return mounted=err==ESP_OK;
}
namespace _Esp32 {
bool OSystem_Esp32::initSDcard(){return prisma_mount_games();}
void OSystem_Esp32::destroySDcard(){}
}
''')
p=up/"main/main.cpp"
s=p.read_text().replace('extern void app_main();','extern int prisma_scumm_run();')
s=s.replace('void app_main(void) {','extern "C" bool prisma_mount_games();\nextern "C" int prisma_scumm_run() {\n  if(!prisma_mount_games())return 1;')
s=s.replace("return;","return 2;") if False else s
# Only change returns in the engine entrypoint, not select_game.
i=s.index('extern "C" int prisma_scumm_run() {')
head,body=s[:i],s[i:]
body=body.replace("return;","return 2;").replace("    abort();","    return 3;")
body=body.replace("  Common::Error result = engine->run();","  printf(\"SC004 ENGINE RUN\\n\");fflush(stdout);\n  Common::Error result = engine->run();")
body=body.replace('  ((_Esp32::OSystem_Esp32*) g_system)->draw_string(30, 50, "Something went wrong...", 0xaffe);','  return 4;')
p.write_text(head+body)
# Engine logs are essential when running on first hardware.
edit(b/"osystem.cpp",lambda s:s.replace("void OSystem_Esp32::logMessage(LogMessageType::Type, const char*) {}",'void OSystem_Esp32::logMessage(LogMessageType::Type, const char* msg) {if(msg)printf("%s",msg);}'))
# Keep original SC003 UI, replacing only runtime handoff. Separate translation units
# avoid Arduino macros/types leaking into old ScummVM headers.
p=root/"src/main.cpp"
s=p.read_text()
a=s.index("bool dos_start(Arduino_RGB_Display& display){")
z=s.index("void setup()",a)
s=s[:a]+'''extern "C" int prisma_scumm_run();
extern "C" void prisma_lcd_row(int x,int y,int w,const uint16_t* row){
    lcd.draw16bitRGBBitmap(x,y,const_cast<uint16_t*>(row),w,1);
}
extern "C" void prisma_lcd_flush(){lcd.flush(true);}
extern "C" bool prisma_touch_sample(int* x,int* y,bool* down){
    pollTouch(); *down=npoints>0;
    if(*down){*x=points[0].x;*y=points[0].y;}
    return true;
}
static volatile bool runtimeActive=false;
static void scummTask(void*){
    int rc=prisma_scumm_run();
    Serial.printf("SC004 ENGINE RETURN rc=%d\\n",rc);Serial.flush();
    lcd.fillScreen(BG);
    RetroUI::center(lcd,240,210,"SCUMMVM STOP",3,0xffff);
    RetroUI::center(lcd,240,250,String("ERROR / FIN ")+rc,2,0x94b2);
    lcd.flush(true);
    // Clean boot after engine return; never reuse live engine globals.
    delay(5000);ESP.restart();vTaskDelete(nullptr);
}
bool dos_start(Arduino_RGB_Display& display){
    Serial.println("SC004 DOS HANDOFF");Serial.flush();
    display.fillScreen(BG);
    RetroUI::center(display,240,210,"CARGANDO...",3,0xffff);
    RetroUI::center(display,240,250,"MONKEY ISLAND",2,0x94b2);
    display.flush(true);
    runtimeActive=true;
    if(xTaskCreatePinnedToCore(scummTask,"scummvm",32768,nullptr,2,nullptr,1)!=pdPASS){
        runtimeActive=false;Serial.println("SC004 TASK ALLOCATION FAILED");homeUI();return false;
    }
    return true;
}
'''+s[z:]
s=s.replace("void loop(){","void loop(){\n  if(runtimeActive){delay(20);return;}")
s=s.replace("SC003","SC004")
p.write_text(s)
edit(root/"src/retro_ui.h",lambda s:s.replace("SC003","SC004"))
# Build exactly the sources from upstream's IDF component manifests, excluding
# LovyanGFX and any unlisted/example source. Preserve all include paths.
dest=root/"src/native"
dest.mkdir()
sources=[]
for component in ["audio","backends","base","cine","common","engines","graphics","gui","image","scumm"]:
    orig=up/"components"/component
    dst=dest/"components"/component
    shutil.copytree(orig,dst)
    cm=(orig/"CMakeLists.txt").read_text()
    match=re.search(r"\bSRCS\s+(.*?)\s+INCLUDE_DIRS",cm,re.S)
    assert match,component
    for src in match.group(1).split():
        q=(dst/src).relative_to(root/"src")
        assert (root/"src"/q).is_file(),q
        sources.append(q.as_posix())
shutil.copytree(up/"main",dest/"main")
sources.append("native/main/main.cpp")
ini=root/"platformio.ini"
s=ini.read_text()
s=s.replace("build_flags = ","build_flags = -Isrc/native -Isrc/native/components -DENABLE_SCUMM_7_8 -fpermissive -Wno-narrowing ")
s+="\nbuild_src_filter = -<*> +<main.cpp>\n"+"\n".join("    +<"+p+">" for p in sources)+"\n"
ini.write_text(s)
print("SC004 selected native sources:",len(sources))

#!/usr/bin/env python3
"""SC002 board adaptation for the pinned upstream revision; fail on unexpected source."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
b=root/"components/backends/platform/esp32"
def edit(path, fn):
    p=root/path
    old=p.read_text()
    new=fn(old)
    assert old!=new, path
    p.write_text(new)
def replace(s,a,b):
    assert s.count(a)==1, a
    return s.replace(a,b,1)
def backend(name,fn): edit("components/backends/platform/esp32/"+name,fn)
def display(s):
    start=s.index("/* ------------------------ LCD pin assignment")
    end=s.index("namespace _Esp32 {",start)
    s=s[:start]+"""#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "driver/uart.h"
#include "freertos/task.h"
#define LCD_ENABLE_OUTPUT
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <lgfx/v1/platforms/esp32s3/Bus_RGB.hpp>
#include <lgfx/v1/platforms/esp32s3/Panel_RGB.hpp>
#define PHYS_SCREEN_WIDTH 320
#define PHYS_SCREEN_HEIGHT 240
class LGFX : public lgfx::LGFX_Device {
    lgfx::Panel_RGB panel;
    lgfx::Bus_RGB bus;
public:
    LGFX() {
        auto p=panel.config();
        p.memory_width=p.panel_width=480;
        p.memory_height=p.panel_height=480;
        p.pin_rst=-1; p.pin_cs=-1; p.offset_rotation=0;
        p.rgb_order=false; p.readable=false;
        panel.config(p);
        auto d=panel.config_detail();
        d.pin_cs=-1; d.pin_sclk=-1; d.pin_mosi=-1; d.use_psram=2;
        panel.config_detail(d);
        auto c=bus.config();
        c.panel=&panel; c.freq_write=8000000;
        c.pin_henable=18; c.pin_vsync=17; c.pin_hsync=16; c.pin_pclk=21;
        // RGB565 low bits blue, then green, then red.
        const int pins[16]={4,5,6,7,15,8,20,3,46,9,10,11,12,13,14,0};
        for(int i=0;i<16;i++) c.pin_data[i]=pins[i];
        c.hsync_pulse_width=8; c.hsync_back_porch=10; c.hsync_front_porch=50;
        c.vsync_pulse_width=8; c.vsync_back_porch=10; c.vsync_front_porch=20;
        c.hsync_polarity=true; c.vsync_polarity=true; c.pclk_active_neg=false;
        bus.config(c); panel.setBus(&bus); setPanel(&panel);
    }
};
"""+s[end:]
    start=s.index("static uint16_t _lcd_addr")
    s=s[:start]+"""static void word9(unsigned v){
    for(int b=8;b>=0;--b){gpio_set_level(GPIO_NUM_48,0);gpio_set_level(GPIO_NUM_47,(v>>b)&1);esp_rom_delay_us(1);gpio_set_level(GPIO_NUM_48,1);esp_rom_delay_us(1);}
}
static void cmd(uint8_t c,const uint8_t* data,int n){
    gpio_set_level(GPIO_NUM_39,0);word9(c);
    for(int i=0;i<n;i++)word9(0x100|data[i]);
    gpio_set_level(GPIO_NUM_39,1);
}
static void panelType9(){
    gpio_set_direction(GPIO_NUM_39,GPIO_MODE_OUTPUT);
    gpio_set_direction(GPIO_NUM_48,GPIO_MODE_OUTPUT);
    gpio_set_direction(GPIO_NUM_47,GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_NUM_39,1);gpio_set_level(GPIO_NUM_48,1);
    cmd(0xFF, (const uint8_t[]){0x77,0x01,0x00,0x00,0x10}, 5);
    cmd(0xC0, (const uint8_t[]){0x3B,0x00}, 2);
    cmd(0xC1, (const uint8_t[]){0x0D,0x02}, 2);
    cmd(0xC2, (const uint8_t[]){0x31,0x05}, 2);
    cmd(0xCD, (const uint8_t[]){0x00}, 1);
    cmd(0xB0, (const uint8_t[]){0x00,0x11,0x18,0x0E,0x11,0x06,0x07,0x08,0x07,0x22,0x04,0x12,0x0F,0xAA,0x31,0x18}, 16);
    cmd(0xB1, (const uint8_t[]){0x00,0x11,0x19,0x0E,0x12,0x07,0x08,0x08,0x08,0x22,0x04,0x11,0x11,0xA9,0x32,0x18}, 16);
    cmd(0xFF, (const uint8_t[]){0x77,0x01,0x00,0x00,0x11}, 5);
    cmd(0xB0, (const uint8_t[]){0x60}, 1);
    cmd(0xB1, (const uint8_t[]){0x32}, 1);
    cmd(0xB2, (const uint8_t[]){0x07}, 1);
    cmd(0xB3, (const uint8_t[]){0x80}, 1);
    cmd(0xB5, (const uint8_t[]){0x49}, 1);
    cmd(0xB7, (const uint8_t[]){0x85}, 1);
    cmd(0xB8, (const uint8_t[]){0x21}, 1);
    cmd(0xC1, (const uint8_t[]){0x78}, 1);
    cmd(0xC2, (const uint8_t[]){0x78}, 1);
    cmd(0xE0, (const uint8_t[]){0x00,0x1B,0x02}, 3);
    cmd(0xE1, (const uint8_t[]){0x08,0xA0,0x00,0x00,0x07,0xA0,0x00,0x00,0x00,0x44,0x44}, 11);
    cmd(0xE2, (const uint8_t[]){0x11,0x11,0x44,0x44,0xED,0xA0,0x00,0x00,0xEC,0xA0,0x00,0x00}, 12);
    cmd(0xE3, (const uint8_t[]){0x00,0x00,0x11,0x11}, 4);
    cmd(0xE4, (const uint8_t[]){0x44,0x44}, 2);
    cmd(0xE5, (const uint8_t[]){0x0A,0xE9,0xD8,0xA0,0x0C,0xEB,0xD8,0xA0,0x0E,0xED,0xD8,0xA0,0x10,0xEF,0xD8,0xA0}, 16);
    cmd(0xE6, (const uint8_t[]){0x00,0x00,0x11,0x11}, 4);
    cmd(0xE7, (const uint8_t[]){0x44,0x44}, 2);
    cmd(0xE8, (const uint8_t[]){0x09,0xE8,0xD8,0xA0,0x0B,0xEA,0xD8,0xA0,0x0D,0xEC,0xD8,0xA0,0x0F,0xEE,0xD8,0xA0}, 16);
    cmd(0xEB, (const uint8_t[]){0x02,0x00,0xE4,0xE4,0x88,0x00,0x40}, 7);
    cmd(0xEC, (const uint8_t[]){0x3C,0x00}, 2);
    cmd(0xED, (const uint8_t[]){0xAB,0x89,0x76,0x54,0x02,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0x20,0x45,0x67,0x98,0xBA}, 16);
    cmd(0xFF, (const uint8_t[]){0x77,0x01,0x00,0x00,0x13}, 5);
    cmd(0xE5, (const uint8_t[]){0xE4}, 1);
    cmd(0xFF, (const uint8_t[]){0x77,0x01,0x00,0x00,0x00}, 5);
    cmd(0x3A, (const uint8_t[]){0x60}, 1);
    cmd(0x11, nullptr, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    cmd(0x29, nullptr, 0);
}
static LGFX lcd;
static bool ready=false;
static uint16_t row[320];
void OSystem_Esp32::backlight_set(int value) {
    if(ready) gpio_set_level(GPIO_NUM_38,value>0);
}
int OSystem_Esp32::is_backlight_initialized(){return ready;}
bool OSystem_Esp32::initDisplay(){
    gpio_set_direction(GPIO_NUM_38,GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_NUM_38,0);
    gpio_set_direction(GPIO_NUM_42,GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_NUM_42,1);
    printf("SC002 LCD TYPE9 begin\\n"); fflush(stdout);
    panelType9();
    printf("SC002 RGB bus begin\\n"); fflush(stdout);
    if(!lcd.init()){printf("SC002 LCD FAIL\\n");return false;}
    lcd.setRotation(0); lcd.setColorDepth(16); lcd.fillScreen(0);
    ready=true; backlight_set(100);
    lcd.fillRect(0,0,160,480,0xF800);lcd.fillRect(160,0,160,480,0x07E0);lcd.fillRect(320,0,160,480,0x001F);
    printf("SC002 RGB bars\\n");fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(2500));
    _screen_width=320; _screen_height=240;
    printf("SC002 LCD READY 480x480\\n");
    return true;
}
void OSystem_Esp32::lcd_set_addr(uint16_t x,uint16_t y,uint16_t w,uint16_t h){
    lcd.setAddrWindow(x,y,w,h);
}
void OSystem_Esp32::destroyDisplay(){}
void OSystem_Esp32::display_send_buf_raw(void* buffer,int w,int h,uint16_t* pal){
    if(!ready || w<=0 || w>320 || h<=0 || h>240)return;
    int left=(480-w)/2,top=(480-h)/2;
    for(int y=0;y<h;y++){
        for(int x=0;x<w;x++){
            row[x]=pal?__builtin_bswap16(pal[((uint8_t*)buffer)[y*w+x]]):((uint16_t*)buffer)[y*w+x];
        }
        lcd.pushImage(left,top+y,w,1,row);
    }
}
void OSystem_Esp32::display_flush(){
    if(!ready || !_gamePixels || !_gameWidth || _gameWidth>320 || !_gameHeight || _gameHeight>240)return;
    const int w=_gameWidth,h=_gameHeight,left=(480-w)/2,top=(480-h)/2;
    const uint16_t* pal=(const uint16_t*)_palette;
    const uint16_t* cp=(const uint16_t*)(_cursorPaletteEnabled?_cursorPalette:_palette);
    int cx=int(getCursorPosX())-_cursorHotspotX,cy=int(getCursorPosY())-_cursorHotspotY;
    static uint32_t frames=0; static int64_t window=0,work=0;
    int64_t t=esp_timer_get_time();
    for(int y=0;y<h;y++){
        for(int x=0;x<w;x++){
            uint16_t color=pal[_gamePixels[y*w+x]];
            if(_mouseBuf && _cursorVisible && x>=cx && y>=cy && x<cx+int(_cursorWidth) && y<cy+int(_cursorHeight)){
                uint8_t v=_mouseBuf[(y-cy)*_cursorWidth+x-cx];
                if(v!=_cursorKeyColor)color=cp[v];
            }
            row[x]=__builtin_bswap16(color);
        }
        lcd.pushImage(left,top+y,w,1,row);
    }
    work+=esp_timer_get_time()-t; ++frames;
    if(!window)window=t;
    if(t-window>=3000000){
        printf("SC002 PERF frames=%lu window_us=%lld draw_avg_us=%lld heap=%lu\\n",(unsigned long)frames,(long long)(t-window),(long long)(work/frames),(unsigned long)esp_get_free_heap_size());
        frames=0;work=0;window=t;
    }
}
} // namespace _Esp32
"""
    return s
backend("osystem-display.cpp",display)
# Replace unsafe joystick driver: no GPIO changes on the RGB pins.
backend("osystem-input.cpp",lambda s:s[:s.index('#include "osystem.h"')]+"""#include "osystem.h"
#include "driver/i2c.h"
namespace _Esp32 {
static uint8_t addr=0;
static esp_err_t rd(uint16_t reg,uint8_t* out,size_t n){
    uint8_t a[2]={(uint8_t)(reg>>8),(uint8_t)reg};
    return i2c_master_write_read_device(I2C_NUM_1,addr,a,2,out,n,pdMS_TO_TICKS(20));
}
bool prismaTouch(int& x,int& y,bool& down){
    if(!addr)return false;
    uint8_t st=0;
    if(rd(0x814e,&st,1)!=ESP_OK || !(st&0x80))return false;
    down=(st&15)!=0;
    uint8_t p[8]={};
    bool ok=!down || rd(0x814f,p,8)==ESP_OK;
    if(down && ok){x=p[1]|(p[2]<<8);y=p[3]|(p[4]<<8);}
    uint8_t clear[]={0x81,0x4e,0};
    i2c_master_write_to_device(I2C_NUM_1,addr,clear,3,pdMS_TO_TICKS(20));
    return ok;
}
bool OSystem_Esp32::isInputInit(){return _isInputInit;}
esp_gamepad_state_t OSystem_Esp32::hw_input_read_raw(){return {};}
void OSystem_Esp32::initInput(){
    i2c_config_t c={}; c.mode=I2C_MODE_MASTER;
    c.sda_io_num=GPIO_NUM_19;c.scl_io_num=GPIO_NUM_45;
    c.sda_pullup_en=GPIO_PULLUP_ENABLE;c.scl_pullup_en=GPIO_PULLUP_ENABLE;
    c.master.clk_speed=400000;
    if(i2c_param_config(I2C_NUM_1,&c)!=ESP_OK ||
       i2c_driver_install(I2C_NUM_1,I2C_MODE_MASTER,0,0,0)!=ESP_OK)return;
    const uint8_t addresses[]={0x5d,0x14};
    for(uint8_t a: addresses){addr=a;uint8_t id[4];if(rd(0x8140,id,4)==ESP_OK){_isInputInit=true;printf("SC002 GT911 READY 0x%02x\\n",a);return;}}
    addr=0;printf("SC002 GT911 NOT FOUND\\n");
}
}
""")
# Synchronous touch event generation avoids the upstream joystick worker and races.
backend("osystem-events.cpp",lambda s:s[:s.index('#include "freertos/FreeRTOS.h"')]+"""#include "osystem.h"
namespace _Esp32 {
bool prismaTouch(int&,int&,bool&);
static int cursorX=160,cursorY=100;
static bool pressed=false;
uint16_t OSystem_Esp32::getCursorPosX(){return cursorX;}
uint16_t OSystem_Esp32::getCursorPosY(){return cursorY;}
void OSystem_Esp32::setCursorPosX(uint16_t x){cursorX=x;}
void OSystem_Esp32::setCursorPosY(uint16_t y){cursorY=y;}
void OSystem_Esp32::get_gamepad_state(esp_gamepad_state_t* s){*s={};}
void OSystem_Esp32::pushEventQueue(Common::Queue<Common::Event>* q,Common::Event& e){q->push(e);}
void OSystem_Esp32::report_keystate_to_engine(){}
void OSystem_Esp32::initEvents(){}
void OSystem_Esp32::destroyEvents(){}
bool OSystem_Esp32::pollEvent(Common::Event& event){
    if(!_eventQueue.empty()){event=_eventQueue.pop();return true;}
    int x=0,y=0;bool down=false;
    if(!prismaTouch(x,y,down))return false;
    const int left=(480-_gameWidth)/2,top=(480-_gameHeight)/2;
    bool inside=x>=left && y>=top && x<left+_gameWidth && y<top+_gameHeight;
    Common::Event e;
    if(down && inside){
        cursorX=x-left;cursorY=y-top;
        e.type=Common::EVENT_MOUSEMOVE;e.mouse.x=cursorX;e.mouse.y=cursorY;
        _eventQueue.push(e);
        if(!pressed){e.type=Common::EVENT_LBUTTONDOWN;_eventQueue.push(e);pressed=true;}
    }else if(!down && pressed){
        e.type=Common::EVENT_LBUTTONUP;e.mouse.x=cursorX;e.mouse.y=cursorY;
        _eventQueue.push(e);pressed=false;
    }
    if(_eventQueue.empty())return false;
    event=_eventQueue.pop();return true;
}
}
""")
# Internal FAT partition, no SD or formatting on mount failure.
backend("osystem-sdcard.cpp",lambda s:s[:s.index('#include "osystem.h"')]+"""#include "osystem.h"
#include "esp_vfs_fat.h"
#include "wear_levelling.h"
namespace _Esp32 {
static wl_handle_t handle=WL_INVALID_HANDLE;
bool OSystem_Esp32::initSDcard(){
    if(handle!=WL_INVALID_HANDLE)return true;
    esp_vfs_fat_mount_config_t cfg={};
    cfg.format_if_mount_failed=false;cfg.max_files=15;cfg.allocation_unit_size=4096;
    esp_err_t err=esp_vfs_fat_spiflash_mount_rw_wl("/flash","games",&cfg,&handle);
    printf("SC002 FLASH FAT %s\\n",esp_err_to_name(err));
    return err==ESP_OK;
}
void OSystem_Esp32::destroySDcard(){
    if(handle!=WL_INVALID_HANDLE){
        esp_vfs_fat_spiflash_unmount_rw_wl("/flash",handle);
        handle=WL_INVALID_HANDLE;
    }
}
}
""")
# Keep engine mixer serviced at real-time cadence, without touching audio hardware.
backend("osystem-audio.cpp",lambda s:s[:s.index('#include "osystem.h"')]+"""#include "osystem.h"
#include "audio/mixer_intern.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
namespace _Esp32 {
static Audio::MixerImpl* mixer=nullptr;
static TaskHandle_t task=nullptr;
static void sink(void*){
    static int16_t samples[800];
    TickType_t last=xTaskGetTickCount();
    for(;;){mixer->mixCallback((byte*)samples,sizeof(samples));vTaskDelayUntil(&last,pdMS_TO_TICKS(20));}
}
void OSystem_Esp32::initAudio(uint32_t rate){
    mixer=new Audio::MixerImpl(g_system,rate);assert(mixer);
    mixer->setReady(true);
    assert(xTaskCreatePinnedToCore(sink,"muteMixer",4096,nullptr,2,&task,0)==pdPASS);
    printf("SC002 AUDIO silent sink; no GPIO\\n");
}
Audio::Mixer* OSystem_Esp32::getMixer(){return mixer;}
void OSystem_Esp32::destroyAudio(){if(task){vTaskDelete(task);task=nullptr;}delete mixer;mixer=nullptr;}
}
""")
backend("osystem.cpp",lambda s:replace(s,"initDisplay();",'printf("SC002 DISPLAY begin\\\\n"); fflush(stdout); if (!initDisplay()) abort();').replace("initGraphics();",'printf("SC002 GRAPHICS begin\\\\n"); fflush(stdout); initGraphics();').replace("initAudio(20000);",'printf("SC002 MIXER begin\\\\n"); fflush(stdout); initAudio(20000);').replace("initInput();",'printf("SC002 INPUT begin\\\\n"); fflush(stdout); initInput();').replace("if (!initSDcard())",'printf("SC002 FLASH begin\\\\n"); fflush(stdout); if (!initSDcard())'))
backend("osystem_gfx.cpp",lambda s:replace(s,"void OSystem_Esp32::warpMouse(int, int) {}","void OSystem_Esp32::warpMouse(int x, int y) { setCursorPosX(x<0?0:x>=_gameWidth?_gameWidth-1:x); setCursorPosY(y<0?0:y>=_gameHeight?_gameHeight-1:y); }"))
# Direct boot to a known folder; no broken joystick selector in this first build.
def main(s):
    a=s.index("void select_game() {");z=s.index("void app_main(void)",a)
    s=s[:a]+"""void select_game() {
    snprintf(base,sizeof(base),"monkey1");
    snprintf(dir,sizeof(dir),"/flash/roms/scummvm/monkey1");
    snprintf(savedir,sizeof(savedir),"/flash/roms/scummvm/monkey1/saves");
    printf("SC002 GAME path=%s\\n",dir);
    ((_Esp32::OSystem_Esp32*)g_system)->setSaveDir(savedir);
}
"""+s[z:]
    s=replace(s,"void app_main(void) {","void app_main(void) {\\n  printf(\"SC002 APP MAIN UART0 115200\\\\n\"); fflush(stdout);")
    s=replace(s,"ConfMan.setBool(\"subtitles\", false);","ConfMan.setBool(\"subtitles\", true);")
    s=replace(s,"  Engine *engine;\n  mEngine->createInstance(g_system, &engine);","  Engine *engine=nullptr;\n  mEngine->createInstance(g_system, &engine);\n  if(!engine){printf(\"SC002 ENGINE INIT FAILED\\n\");return;}")
    return s
edit("main/main.cpp",main)
# Stable flash settings, factory slot 6 MiB; no private data packed in SC002.
p=root/"sdkconfig"
s=p.read_text()
s=replace(s,"CONFIG_ESPTOOLPY_FLASHFREQ_80M=y","# CONFIG_ESPTOOLPY_FLASHFREQ_80M is not set")
s=replace(s,"# CONFIG_ESPTOOLPY_FLASHFREQ_40M is not set","CONFIG_ESPTOOLPY_FLASHFREQ_40M=y")
s=replace(s,'CONFIG_ESPTOOLPY_FLASHFREQ="80m"','CONFIG_ESPTOOLPY_FLASHFREQ="40m"')
s=replace(s,"CONFIG_ESPTOOLPY_FLASHMODE_QIO=y","# CONFIG_ESPTOOLPY_FLASHMODE_QIO is not set")
s=replace(s,"# CONFIG_ESPTOOLPY_FLASHMODE_DIO is not set","CONFIG_ESPTOOLPY_FLASHMODE_DIO=y")
p.write_text(s)
(root/"partitions.csv").write_text("""# Name,Type,SubType,Offset,Size
nvs,data,nvs,0x9000,0x6000
phy_init,data,phy,0xf000,0x1000
factory,app,factory,0x10000,0x600000
games,data,fat,0x610000,0x9F0000
""")
# Remove unused PWM component and stale registry metadata.
import shutil
manifest=root/"main/idf_component.yml"
manifest.write_text('dependencies:\n  idf:\n    version: ">=5.2.1,<5.3"\n')
shutil.rmtree(root/"managed_components",ignore_errors=True)
(root/"dependencies.lock").unlink(missing_ok=True)
# FAT image is generated with the same ESP-IDF version as the firmware.
with (root/"main/CMakeLists.txt").open("a") as cm:
    cm.write('\nfatfs_create_spiflash_image(games "'+chr(36)+'{CMAKE_SOURCE_DIR}/game_data" FLASH_IN_PROJECT)\n')
(root/"game_data/roms/scummvm/monkey1/saves").mkdir(parents=True,exist_ok=True)
(root/"game_data/roms/scummvm/monkey1/README.txt").write_text("Place your original 000.LFL, 901-904.LFL and DISK01-04.LEC files here before packing.\n")
edit("main/main.cpp",lambda s:replace(s,"  assert(dirNode.getChildren(files, Common::FSNode::kListAll));",'''  if(!dirNode.getChildren(files, Common::FSNode::kListAll)){
    printf("SC002 GAME DIRECTORY MISSING\\n");return;
  }'''.replace('MISSING\\n','MISSING\\\\n')).replace('    abort();','    return;'))
print("SC002 board adaptation applied")

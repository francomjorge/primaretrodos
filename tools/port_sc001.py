#!/usr/bin/env python3
"""SC001 board adaptation for the pinned upstream revision; fail on unexpected source."""
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
#define LCD_ENABLE_OUTPUT
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <lgfx/v1/platforms/esp32s3/Bus_RGB.hpp>
#include <lgfx/v1/platforms/esp32s3/Panel_RGB.hpp>
#define PHYS_SCREEN_WIDTH 320
#define PHYS_SCREEN_HEIGHT 240
class LGFX : public lgfx::LGFX_Device {
    lgfx::Panel_ST7701 panel;
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
        d.pin_cs=39; d.pin_sclk=48; d.pin_mosi=47; d.use_psram=2;
        panel.config_detail(d);
        auto c=bus.config();
        c.panel=&panel; c.freq_write=8000000;
        c.pin_henable=18; c.pin_vsync=17; c.pin_hsync=16; c.pin_pclk=21;
        // RGB565 low bits blue, then green, then red.
        const int pins[16]={4,5,6,7,15,0,8,20,3,46,9,10,11,12,13,14};
        for(int i=0;i<16;i++) c.pin_data[i]=pins[i];
        c.hsync_pulse_width=8; c.hsync_back_porch=10; c.hsync_front_porch=50;
        c.vsync_pulse_width=8; c.vsync_back_porch=10; c.vsync_front_porch=20;
        c.hsync_polarity=true; c.vsync_polarity=true; c.pclk_active_neg=false;
        bus.config(c); panel.setBus(&bus); setPanel(&panel);
    }
};
"""+s[end:]
    start=s.index("static uint16_t _lcd_addr")
    s=s[:start]+"""static LGFX lcd;
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
    if(!lcd.init()){printf("SC001 LCD FAIL\\n");return false;}
    lcd.setRotation(0); lcd.setColorDepth(16); lcd.fillScreen(0);
    ready=true; backlight_set(100);
    _screen_width=320; _screen_height=240;
    printf("SC001 LCD READY 480x480\\n");
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
        printf("SC001 PERF frames=%lu window_us=%lld draw_avg_us=%lld heap=%lu\\n",(unsigned long)frames,(long long)(t-window),(long long)(work/frames),(unsigned long)esp_get_free_heap_size());
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
    for(uint8_t a: {0x5d,0x14}){addr=a;uint8_t id[4];if(rd(0x8140,id,4)==ESP_OK){_isInputInit=true;printf("SC001 GT911 READY 0x%02x\\n",a);return;}}
    addr=0;printf("SC001 GT911 NOT FOUND\\n");
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
# SD SPI: keep LCD command CS high; never format.
backend("osystem-sdcard.cpp",lambda s:s[:s.index('#include "osystem.h"')]+"""#include "osystem.h"
#include "esp_vfs_fat.h"
#include "driver/spi_master.h"
#include "driver/sdspi_host.h"
#include "driver/gpio.h"
#include "sdmmc_cmd.h"
namespace _Esp32 {
static sdmmc_card_t* card=nullptr;
bool OSystem_Esp32::initSDcard(){
    if(card)return true;
    gpio_set_direction(GPIO_NUM_39,GPIO_MODE_OUTPUT);gpio_set_level(GPIO_NUM_39,1);
    spi_bus_config_t bus={};bus.mosi_io_num=47;bus.miso_io_num=41;bus.sclk_io_num=48;
    bus.quadwp_io_num=-1;bus.quadhd_io_num=-1;bus.max_transfer_sz=4096;
    if(spi_bus_initialize(SPI2_HOST,&bus,SPI_DMA_CH_AUTO)!=ESP_OK)return false;
    sdmmc_host_t host=SDSPI_HOST_DEFAULT();host.slot=SPI2_HOST;host.max_freq_khz=5000;
    sdspi_device_config_t slot=SDSPI_DEVICE_CONFIG_DEFAULT();slot.host_id=SPI2_HOST;slot.gpio_cs=GPIO_NUM_42;
    esp_vfs_fat_sdmmc_mount_config_t cfg={};cfg.format_if_mount_failed=false;cfg.max_files=15;
    esp_err_t err=esp_vfs_fat_sdspi_mount("/sd",&host,&slot,&cfg,&card);
    printf("SC001 SD %s\\n",esp_err_to_name(err));return err==ESP_OK;
}
void OSystem_Esp32::destroySDcard(){if(card){esp_vfs_fat_sdcard_unmount("/sd",card);card=nullptr;spi_bus_free(SPI2_HOST);}}
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
    printf("SC001 AUDIO silent sink; no GPIO\\n");
}
Audio::Mixer* OSystem_Esp32::getMixer(){return mixer;}
void OSystem_Esp32::destroyAudio(){if(task){vTaskDelete(task);task=nullptr;}delete mixer;mixer=nullptr;}
}
""")
backend("osystem.cpp",lambda s:replace(s,"initDisplay();","if (!initDisplay()) abort();"))
backend("osystem_gfx.cpp",lambda s:replace(s,"void OSystem_Esp32::warpMouse(int, int) {}","void OSystem_Esp32::warpMouse(int x, int y) { setCursorPosX(x<0?0:x>=_gameWidth?_gameWidth-1:x); setCursorPosY(y<0?0:y>=_gameHeight?_gameHeight-1:y); }"))
# Direct boot to a known folder; no broken joystick selector in this first build.
def main(s):
    a=s.index("void select_game() {");z=s.index("void app_main(void)",a)
    s=s[:a]+"""void select_game() {
    snprintf(base,sizeof(base),"monkey1");
    snprintf(dir,sizeof(dir),"/sd/roms/scummvm/monkey1");
    snprintf(savedir,sizeof(savedir),"%s/saves",dir);
    printf("SC001 GAME path=%s\\n",dir);
    ((_Esp32::OSystem_Esp32*)g_system)->setSaveDir(savedir);
}
"""+s[z:]
    s=replace(s,"ConfMan.setBool(\"subtitles\", false);","ConfMan.setBool(\"subtitles\", true);")
    s=replace(s,"  Engine *engine;\n  mEngine->createInstance(g_system, &engine);","  Engine *engine=nullptr;\n  mEngine->createInstance(g_system, &engine);\n  if(!engine){printf(\"SC001 ENGINE INIT FAILED\\n\");return;}")
    return s
edit("main/main.cpp",main)
# Stable flash settings, factory slot 6 MiB; no private data packed in SC001.
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
storage,data,spiffs,0x610000,0x3F0000
""")
print("SC001 board adaptation applied")

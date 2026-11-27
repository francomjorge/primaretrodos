#!/usr/bin/env python3
"""SC024: read game folders from microSD SPI, retain flash game and internal saves.
Based on compiled SC023, intentionally excludes native hi-res SC018.
"""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'#include <Wire.h>','#include <Wire.h>\n#include <SPI.h>\n#include <SD.h>\n#include <dirent.h>\n#include <sys/stat.h>')
s=rep(s,'static void homeUI(){',r'''static constexpr int maxSDGames=64;
static char sdGames[maxSDGames][64];
static unsigned sdCount=0,catalogIndex=0;
static bool sdMounted=false,sdTruncated=false;
static void scanSD(){
    sdCount=0;sdTruncated=false;catalogIndex=0;
    // ST7701 initialization has finished; its command CS must stay inactive.
    pinMode(39,OUTPUT);digitalWrite(39,HIGH);
    pinMode(42,OUTPUT);digitalWrite(42,HIGH);
    if(!sdMounted){
        SPI.begin(48,41,47,42);
        sdMounted=SD.begin(42,SPI,10000000,"/sd",10,false);
    }
    if(!sdMounted)return;
    DIR* dir=opendir("/sd/roms/scummvm");
    if(!dir)return;
    while(auto* entry=readdir(dir)){
        const char* n=entry->d_name;
        if(n[0]=='.'||!n[0]||strlen(n)>=sizeof(sdGames[0]))continue;
        char path[160];snprintf(path,sizeof(path),"/sd/roms/scummvm/%s",n);
        struct stat st;
        if(stat(path,&st)!=0||!S_ISDIR(st.st_mode))continue;
        if(sdCount==maxSDGames){sdTruncated=true;break;}
        snprintf(sdGames[sdCount++],sizeof(sdGames[0]),"%s",n);
    }
    closedir(dir);
    for(unsigned i=1;i<sdCount;i++){
        for(unsigned j=i;j>0&&strcasecmp(sdGames[j],sdGames[j-1])<0;j--){
            char tmp[64];memcpy(tmp,sdGames[j],64);memcpy(sdGames[j],sdGames[j-1],64);memcpy(sdGames[j-1],tmp,64);
        }
    }
}
extern "C" bool prisma_game_from_sd(){return catalogIndex>0&&catalogIndex<=sdCount;}
extern "C" void prisma_game_choice(char* target,char* path){
    if(!prisma_game_from_sd()){
        snprintf(target,256,"monkey1");
        snprintf(path,256,"/flash/roms/scummvm/monkey1");
        return;
    }
    const char* name=sdGames[catalogIndex-1];
    // Stable FAT-safe target name, distinct from the existing flash save prefix.
    uint32_t hash=2166136261u;
    for(const unsigned char* q=(const unsigned char*)name;*q;q++){
        unsigned c=*q;if(c>='A'&&c<='Z')c+=32;
        hash=(hash^c)*16777619u;
    }
    snprintf(target,256,"sd%08lx",(unsigned long)hash);
    snprintf(path,256,"/sd/roms/scummvm/%s",name);
}
static void homeUI(){''')
# Catalog index and count reflect directories; detection of actual game is native.
a=s.index('static void drawScummCarousel(){')
b=s.index('static void scummTask(',a)
t=s[a:b]
t=rep(t,'RetroUI::text(d,114,39,"1 JUEGO / FLASH INTERNA",1,0x9cfa);',r'''char summary[48];
    snprintf(summary,sizeof(summary),"1 FLASH / %u SD%s",sdCount,sdTruncated?"+":"");
    RetroUI::text(d,114,39,summary,1,0x9cfa);''')
t=rep(t,'    uint16_t coverRow[256];','    if(!prisma_game_from_sd()){\n    uint16_t coverRow[256];')
t=rep(t,'    RetroUI::center(d,240,382,"VGA / 256 COLORES",1,0x9cfa);',r'''    RetroUI::center(d,240,382,"VGA / 256 COLORES / FLASH",1,0x9cfa);
    }else{
        RetroUI::console(d,138,122,6,0);
        RetroUI::center(d,240,302,"MICROSD",2,0x5e9e);
        char title[29];snprintf(title,sizeof(title),"%.28s",sdGames[catalogIndex-1]);
        RetroUI::center(d,240,350,title,1,0xffff);
        RetroUI::center(d,240,382,"DETECCION AL INICIAR",1,0x9cfa);
    }
    if(!sdMounted)RetroUI::center(d,240,421,"SD NO DISPONIBLE",1,0xfbe0);
    else if(!sdCount)RetroUI::center(d,240,421,"SD OK / SIN CARPETAS",1,0xbdf7);
    else RetroUI::center(d,240,421,"SD OK / FAT32",1,0x07e0);''')
t=rep(t,'    RetroUI::center(d,240,444,"1/1",2,0x9cfa);','    snprintf(summary,sizeof(summary),"%u/%u",catalogIndex+1,sdCount+1);\n    RetroUI::center(d,240,444,summary,2,0x9cfa);')
s=s[:a]+t+s[b:]
s=rep(s,'if(!selected&&hit(p,16,90,448,148)){drawScummCarousel();}',r'''if(!selected&&hit(p,16,90,448,148)){scanSD();drawScummCarousel();}''')
s=rep(s,'else if(selected&&hit(p,12,10,90,44))homeUI();',r'''else if(selected&&hit(p,12,10,90,44))homeUI();
      else if(selected&&hit(p,6,184,44,84)){catalogIndex=(catalogIndex+sdCount)%(sdCount+1);drawScummCarousel();}
      else if(selected&&hit(p,430,184,44,84)){catalogIndex=(catalogIndex+1)%(sdCount+1);drawScummCarousel();}''')
# Show title image only for the internal Monkey Island; other games use a neutral transition.
s=rep(s,'    uint16_t row[384];\n    for(int y=0;y<294;y++){','    uint16_t row[384];\n    if(!prisma_game_from_sd())for(int y=0;y<294;y++){')
s=rep(s,'    RetroUI::center(lcd,240,350,action==1?"GUARDANDO PARTIDA":"CARGANDO PARTIDA",2,0xffff);',
'''    if(prisma_game_from_sd())RetroUI::center(lcd,240,180,"PRISMA / SCUMMVM",3,0xffff);
    RetroUI::center(lcd,240,350,action==1?"GUARDANDO PARTIDA":"CARGANDO PARTIDA",2,0xffff);''')
# Same boot partition and renderer. Do not ever format an SD automatically.
p.write_text(s.replace("SC023","SC024"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC023","SC024"))
p=src/"native/main/main.cpp";s=p.read_text()
s='extern "C" void prisma_game_choice(char*,char*);\nextern "C" bool prisma_game_from_sd();\n'+s
s=rep(s,'    snprintf(base,sizeof(base),"monkey1");\n    snprintf(dir,sizeof(dir),"/flash/roms/scummvm/monkey1");','    prisma_game_choice(base,dir);')
s=rep(s,'  assert(dirNode.getChildren(files, Common::FSNode::kListAll));','  if(!dirNode.getChildren(files, Common::FSNode::kListAll))return 6;')
# Initial SD release explicitly limits SCUMM to known low-resolution DOS games.
# Full Throttle and other variants will be enabled after separate tests.
s=rep(s,'  ConfMan.set("gameid", games[0].gameId, base);',r'''  if(prisma_game_from_sd()){
    const Common::String& id=games[0].gameId;
    if(id!="monkey"&&id!="monkey2"&&id!="tentacle"&&id!="indy4"&&id!="samnmax"
        &&id!="loom"&&id!="indy3"&&id!="zak"&&id!="maniac"){
        printf("SC024 GAME NOT ENABLED: %s\n",id.c_str());return 7;
    }
  }
  ConfMan.set("gameid", games[0].gameId, base);''')
p.write_text(s)
# SD games still use the internal save volume, isolated by target prefix.
# If the internal games volume is unavailable, SD remains usable.
p=src/"native/components/backends/platform/esp32/osystem-sdcard.cpp";s=p.read_text()
s=rep(s,'static bool mounted=false,savesMounted=false;','extern "C" bool prisma_game_from_sd();\nstatic bool mounted=false,savesMounted=false;')
s=rep(s,'    if(mounted)return true;','    if(mounted)return true;')
s=rep(s,'mounted=err==ESP_OK;if(mounted)mountSaves();return mounted;','mounted=err==ESP_OK;mountSaves();return mounted||prisma_game_from_sd();')
p.write_text(s)
# Guard against any detector variant that requests more than our current buffer.
p=src/"native/components/backends/platform/esp32/osystem_gfx.cpp";s=p.read_text()
s=rep(s,'void OSystem_Esp32::initSize(uint width, uint height, const Graphics::PixelFormat *format) {',
'''void OSystem_Esp32::initSize(uint width, uint height, const Graphics::PixelFormat *format) {
    if(!width||!height||width>320||height>240||(format&&format->bytesPerPixel!=1)){
        printf("SC024 UNSUPPORTED RESOLUTION %u x %u\\n",width,height);abort();
    }''')
p.write_text(s)
print("SC024: SD SPI 42/47/41/48, FAT folder catalog, fixed flash entry, separate internal save targets, low-res guard; no formatting")

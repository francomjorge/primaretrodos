#!/usr/bin/env python3
"""SC013: F5 custom touch save/load overlay, numeric and optional name entry."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);src=root/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
# The game partition remains byte-identical and at the same offset.
p=root/"partitions_scumm.csv";s=p.read_text()
s=rep(s,"factory,app,factory,0x10000,0x600000","factory,app,factory,0x10000,0x500000\nsaves,data,fat,0x510000,0x100000")
p.write_text(s)
p=src/"native/components/backends/platform/esp32/osystem-sdcard.cpp";s=p.read_text()
s=rep(s,'#include "esp_vfs_fat.h"','#include "esp_vfs_fat.h"\n#include "esp_partition.h"\n#include "wear_levelling.h"')
s=rep(s,'static bool mounted=false;',r'''static bool mounted=false,savesMounted=false;
static wl_handle_t saveHandle=WL_INVALID_HANDLE;
extern "C" void prisma_diag_line(int,const char*,...);
extern "C" bool prisma_save_ready(){return savesMounted;}
static bool blankSavePartition(const esp_partition_t* p){
    if(!p)return false;
    uint8_t b[256];
    // Never format an existing volume automatically after a mount error.
    for(size_t off=0;off<p->size;off+=sizeof(b)){
        if(esp_partition_read(p,off,b,sizeof(b))!=ESP_OK)return false;
        for(unsigned i=0;i<sizeof(b);i++)if(b[i]!=0xff)return false;
    }
    return true;
}
static void mountSaves(){
    if(savesMounted)return;
    esp_vfs_fat_mount_config_t cfg={};cfg.max_files=8;cfg.allocation_unit_size=4096;
    esp_err_t rc=esp_vfs_fat_spiflash_mount_rw_wl("/saves","saves",&cfg,&saveHandle);
    if(rc!=ESP_OK){
        const auto* p=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_FAT,"saves");
        if(blankSavePartition(p)){
            cfg.format_if_mount_failed=true;
            rc=esp_vfs_fat_spiflash_mount_rw_wl("/saves","saves",&cfg,&saveHandle);
        }
    }
    savesMounted=rc==ESP_OK;
    prisma_diag_line(2,"SAVE STORAGE %s",esp_err_to_name(rc));
}
''')
# Check blankness before the first mount: WL initialization may write metadata.
s=s.replace('    esp_err_t rc=esp_vfs_fat_spiflash_mount_rw_wl("/saves","saves",&cfg,&saveHandle);\n    if(rc!=ESP_OK){\n        const auto* p=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_FAT,"saves");\n        if(blankSavePartition(p)){\n            cfg.format_if_mount_failed=true;\n            rc=esp_vfs_fat_spiflash_mount_rw_wl("/saves","saves",&cfg,&saveHandle);\n        }\n    }','    const auto* p=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_FAT,"saves");\n    if(!p)return;\n    cfg.format_if_mount_failed=blankSavePartition(p);\n    esp_err_t rc=esp_vfs_fat_spiflash_mount_rw_wl("/saves","saves",&cfg,&saveHandle);')
s=rep(s,'return mounted=err==ESP_OK;','mounted=err==ESP_OK;if(mounted)mountSaves();return mounted;')
p.write_text(s)
p=src/"native/main/main.cpp";s=p.read_text()
s=rep(s,'"/flash/roms/scummvm/monkey1/saves"','"/saves"')
p.write_text(s)
# Reuse the engine's own save/load request methods, at its existing F5
# handling point. Never instantiate its unimplemented upstream GUI.
p=src/"native/components/scumm/input.cpp";s=p.read_text()
s='extern "C" bool prisma_save_ready();\nextern "C" int prisma_save_menu(int*,char*,const char*,bool,bool,bool);\n'+s
s=rep(s,'\t\topenMainMenuDialog();\t\t// Display global main menu',r'''        char slots[9][32]={};
        const bool storage=prisma_save_ready();
        if(storage)for(int i=0;i<9;i++){
            Common::String desc;
            if(getSavegameName(i+1,desc)){
                snprintf(slots[i],sizeof(slots[i]),"%s",desc.c_str());
                if(!slots[i][0])snprintf(slots[i],sizeof(slots[i]),"PARTIDA %d",i+1);
            }
        }
        int slot=1;char name[32]={};
        pauseEngine(true);
        int action=prisma_save_menu(&slot,name,&slots[0][0],storage,
            canSaveGameStateCurrently(),canLoadGameStateCurrently());
        pauseEngine(false);
        if(action==1&&storage&&canSaveGameStateCurrently())saveGameState(slot,Common::String(name));
        if(action==2&&storage&&canLoadGameStateCurrently())loadGameState(slot);
''')
p.write_text(s)
# Return actual outcome to next F5 overlay; no streaming console.
p=src/"native/components/scumm/scumm.cpp";s=p.read_text()
s='extern "C" void prisma_save_outcome(int,int,bool);\n'+s
s=rep(s,'\t\tif (!success) {\n\t\t\tdisplayMessage(0, errMsg, filename.c_str());','''        if(!_saveTemporaryState&&_saveLoadSlot>=1&&_saveLoadSlot<=9)
            prisma_save_outcome(_saveLoadFlag,_saveLoadSlot,success);
        if (!success) {
            // The original GUI is unavailable on this port.
            if(_saveTemporaryState)displayMessage(0, errMsg, filename.c_str());''')
p.write_text(s)
p=src/"main.cpp";s=p.read_text()
anchor='static volatile bool runtimeActive=false;'
ui=r'''
// Modal overlay: same LCD owner, no game resize, restore original pixels
// on dismissal. No persistent keyboard or second rendering task.
struct SaveKey {int x,y,w,h,id;const char* label;};
static char saveOutcome[48]={};
extern "C" void prisma_save_outcome(int action,int slot,bool ok){
    snprintf(saveOutcome,sizeof(saveOutcome),"%s %d: %s",action==1?"GUARDAR":"CARGAR",slot,ok?"OK":"ERROR");
    prisma_diag_line(2,"%s",saveOutcome);
}
extern "C" int prisma_save_menu(int* resultSlot,char* resultName,const char* names,bool storage,bool canSave,bool canLoad){
    constexpr int top=205,rows=480-top;
    uint16_t* fb=lcd.getFramebuffer();
    if(!fb)return 0;
    uint16_t* backup=(uint16_t*)heap_caps_malloc(480*rows*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!backup)return 0;
    memcpy(backup,fb+top*480,480*rows*2);
    int slot=1,action=0;bool alpha=false,overwrite=false,done=false;
    char name[32]={},status[48]={};
    snprintf(status,sizeof(status),"%s",storage?saveOutcome:"FLASH PARTIDAS NO DISPONIBLE");
    auto setName=[&](){
        const char* old=names+(slot-1)*32;
        if(*old)snprintf(name,sizeof(name),"%s",old);
        else snprintf(name,sizeof(name),"PARTIDA %d",slot);
        overwrite=false;
    };
    setName();
    SaveKey keys[48];unsigned nk=0;
    auto key=[&](int x,int y,int w,int h,int id,const char* label){
        keys[nk++]={x,y,w,h,id,label};
        lcd.fillRoundRect(x+2,y+2,w-4,h-4,4,0x2124);
        lcd.drawRoundRect(x+2,y+2,w-4,h-4,4,0x7bef);
        int sz=(int(strlen(label))*12<w-6)?2:1;
        lcd.setTextSize(sz);lcd.setTextColor(0xffff);
        lcd.setCursor(x+(w-int(strlen(label))*6*sz)/2,y+(h-8*sz)/2);lcd.print(label);
    };
    auto draw=[&](){
        nk=0;
        lcd.fillRect(0,top,480,rows,0x0842);
        RetroUI::text(lcd,10,top+8,"F5 / PARTIDAS",2,0xffff);
        key(340,top,140,32,100,"OCULTAR");
        key(0,top+34,52,38,101,"<");
        key(52,top+34,52,38,102,">");
        char slotLabel[44];snprintf(slotLabel,sizeof(slotLabel),"%d/9 %s",slot,names[(slot-1)*32]?"OCUPADO":"LIBRE");
        RetroUI::text(lcd,112,top+43,slotLabel,2,0xffff);
        key(0,top+73,235,36,103,overwrite?"CONFIRMAR":"GUARDAR");
        key(235,top+73,245,36,104,"CARGAR");
        lcd.fillRect(4,top+112,472,28,0x0000);
        RetroUI::text(lcd,8,top+116,name,1,0xffff);
        RetroUI::text(lcd,8,top+144,status,1,0xffe0);
        // Two compact keypad modes: default numeric, optional alphabet for names.
        static const char letters[]="QWERTYUIOPASDFGHJKLZXCVBNM";
        static const char nums[]="1234567890";
        static char glyphs[36][2];
        if(alpha){
            for(int i=0;i<26;i++){
                glyphs[i][0]=letters[i];glyphs[i][1]=0;
                int r=i/10,c=i%10;key(c*48,top+160+r*28,48,28,letters[i],glyphs[i]);
            }
            key(288,top+216,96,28,105,"123");
            key(384,top+216,96,28,106,"BORRAR");
        }else{
            for(int i=0;i<10;i++){
                glyphs[i][0]=nums[i];glyphs[i][1]=0;
                key((i%5)*96,top+160+(i/5)*42,96,42,nums[i],glyphs[i]);
            }
            key(0,top+244,96,31,105,"ABC");
            key(96,top+244,192,31,107,"ESPACIO");
            key(288,top+244,192,31,106,"BORRAR");
        }
        if(alpha){key(0,top+244,240,31,107,"ESPACIO");key(240,top+244,240,31,108,"LIMPIAR");}
        lcd.flush(true);
    };
    draw();
    // Three-finger F5 was generated on release. Require a new clean tap.
    bool finger=false,blocked=false;int chosen=-1;
    while(!done){
        prisma_diag_poll();pollTouch();
        if(npoints>1){blocked=true;finger=false;chosen=-1;}
        else if(blocked){if(!npoints)blocked=false;}
        else if(npoints==1&&!finger){
            finger=true;chosen=-1;int x=points[0].x,y=points[0].y;
            for(unsigned i=0;i<nk;i++)if(x>=keys[i].x&&y>=keys[i].y&&x<keys[i].x+keys[i].w&&y<keys[i].y+keys[i].h){chosen=keys[i].id;break;}
        }else if(!npoints&&finger){
            finger=false;int k=chosen;chosen=-1;
            if(k==100){done=true;}
            else if(k==101||k==102){slot=(slot-1+(k==101?8:1))%9+1;setName();draw();}
            else if(k==103){
                if(!storage||!canSave)snprintf(status,sizeof(status),"GUARDAR NO DISPONIBLE AHORA");
                else if(names[(slot-1)*32]&&!overwrite){overwrite=true;snprintf(status,sizeof(status),"CONFIRMAR SOBREESCRITURA");}
                else{action=1;done=true;}
                if(!done)draw();
            }else if(k==104){
                if(storage&&canLoad&&names[(slot-1)*32]){action=2;done=true;}
                else{snprintf(status,sizeof(status),"PARTIDA NO DISPONIBLE");draw();}
            }else if(k==105){alpha=!alpha;draw();}
            else if(k==106||k==107||k==108||(k>=32&&k<=90)){
                size_t n=strlen(name);
                if(k==106){if(n)name[n-1]=0;}
                else if(k==108)name[0]=0;
                else if(n<30){name[n]=k==107?' ':char(k);name[n+1]=0;}
                overwrite=false;draw();
            }
        }
        delay(12);
    }
    memcpy(fb+top*480,backup,480*rows*2);free(backup);
    lcd.flush(true);indexedValid=false;
    *resultSlot=slot;if(!name[0])snprintf(name,sizeof(name),"PARTIDA %d",slot);
    snprintf(resultName,32,"%s",name);
    return action;
}
'''
# Arrow and numeric/alpha geometry was verified by shared hitbox table.
s=rep(s,anchor,ui+'\n'+anchor)
p.write_text(s.replace("SC012","SC013"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC012","SC013"))
print("SC013: fullscreen F5 modal, native save/load, separate 1 MiB writable saves volume; no change to game partition")

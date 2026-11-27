#!/usr/bin/env python3
"""SC014: four large save cards. Keep SC013 storage and engine untouched."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);src=root/"src"
p=src/"main.cpp";s=p.read_text()
a=s.index('extern "C" int prisma_save_menu(')
b=s.index('static volatile bool runtimeActive=false;',a)
s=s[:a]+r'''
extern "C" int prisma_save_menu(int* resultSlot,char* resultName,const char* names,bool storage,bool canSave,bool canLoad){
    constexpr int top=205,rows=480-top;
    uint16_t* fb=lcd.getFramebuffer();
    if(!fb)return 0;
    uint16_t* backup=(uint16_t*)heap_caps_malloc(480*rows*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!backup)return 0;
    memcpy(backup,fb+top*480,480*rows*2);
    int slot=1,action=0;bool overwrite=false,done=false;
    char status[64]={};
    snprintf(status,sizeof(status),"%s",storage?saveOutcome:"FLASH PARTIDAS NO DISPONIBLE");
    SaveKey keys[8];unsigned nk=0;
    auto occupied=[&](int n){return names[(n-1)*32]!=0;};
    auto key=[&](int x,int y,int w,int h,int id,const char* label,bool enabled){
        if(enabled)keys[nk++]={x,y,w,h,id,label};
        lcd.fillRoundRect(x+2,y+2,w-4,h-4,5,enabled?0x2124:0x18e3);
        lcd.drawRoundRect(x+2,y+2,w-4,h-4,5,enabled?0x7bef:0x39e7);
        int sz=(int(strlen(label))*12<w-8)?2:1;
        lcd.setTextSize(sz);lcd.setTextColor(enabled?0xffff:0x7bef);
        lcd.setCursor(x+(w-int(strlen(label))*6*sz)/2,y+(h-8*sz)/2);lcd.print(label);
    };
    auto draw=[&](){
        nk=0;lcd.fillRect(0,top,480,rows,0x0842);
        RetroUI::text(lcd,10,top+10,"F5 / PARTIDAS",2,0xffff);
        key(340,top+2,136,36,100,"OCULTAR",true);
        for(int i=0;i<4;i++){
            int n=i+1,x=6+(i%2)*237,y=top+42+(i/2)*84,w=231,h=78;
            bool used=occupied(n),selected=n==slot;
            keys[nk++]={x,y,w,h,n,nullptr};
            uint16_t bg=used?0x0328:0x2945;
            lcd.fillRoundRect(x,y,w,h,6,bg);
            lcd.drawRoundRect(x,y,w,h,6,selected?0xffe0:(used?0x4e69:0x630c));
            if(selected)lcd.drawRoundRect(x+1,y+1,w-2,h-2,5,0xffe0);
            char label[24];snprintf(label,sizeof(label),"PARTIDA %d",n);
            RetroUI::text(lcd,x+12,y+12,label,2,0xffff);
            RetroUI::text(lcd,x+12,y+42,used?"GUARDADA":"VACIA",2,used?0xaff5:0xbdf7);
            // Preserve and display a custom name from SC013, without editing it.
            if(used&&strcmp(names+i*32,label)){
                char shortName[29];snprintf(shortName,sizeof(shortName),"%.28s",names+i*32);
                RetroUI::text(lcd,x+12,y+63,shortName,1,0xffff);
            }
        }
        key(4,top+211,234,38,103,overwrite?"CONFIRMAR":occupied(slot)?"SOBRESCRIBIR":"GUARDAR",storage&&canSave);
        key(242,top+211,234,38,104,"CARGAR",storage&&canLoad&&occupied(slot));
        RetroUI::text(lcd,8,top+259,status,1,0xffe0);
        lcd.flush(true);
    };
    draw();
    bool finger=false,blocked=false;int chosen=-1;
    auto hit=[&](int x,int y){
        for(unsigned i=0;i<nk;i++)if(x>=keys[i].x&&y>=keys[i].y&&x<keys[i].x+keys[i].w&&y<keys[i].y+keys[i].h)return keys[i].id;
        return -1;
    };
    while(!done){
        prisma_diag_poll();pollTouch();
        if(npoints>1){blocked=true;finger=false;chosen=-1;}
        else if(blocked){if(!npoints)blocked=false;}
        else if(npoints==1&&!finger){finger=true;chosen=hit(points[0].x,points[0].y);}
        else if(npoints==1&&finger&&hit(points[0].x,points[0].y)!=chosen){chosen=-1;}
        else if(!npoints&&finger){
            finger=false;int k=chosen;chosen=-1;
            if(k==100)done=true;
            else if(k>=1&&k<=4){
                slot=k;overwrite=false;
                snprintf(status,sizeof(status),"%s",storage?(occupied(slot)?"PARTIDA GUARDADA":"RANURA DISPONIBLE"):"FLASH PARTIDAS NO DISPONIBLE");
                draw();
            }else if(k==103&&storage&&canSave){
                if(occupied(slot)&&!overwrite){overwrite=true;snprintf(status,sizeof(status),"TOCAR CONFIRMAR PARA REEMPLAZAR");draw();}
                else{action=1;done=true;}
            }else if(k==104&&storage&&canLoad&&occupied(slot)){action=2;done=true;}
        }
        delay(12);
    }
    memcpy(fb+top*480,backup,480*rows*2);free(backup);
    lcd.flush(true);indexedValid=false;
    *resultSlot=slot;
    if(occupied(slot))snprintf(resultName,32,"%s",names+(slot-1)*32);
    else snprintf(resultName,32,"PARTIDA %d",slot);
    return action;
}
'''+s[b:]
p.write_text(s.replace("SC013","SC014"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC013","SC014"))
# Keep nine-slot engine ABI and old save files. Only scan/display first four.
p=src/"native/components/scumm/input.cpp";s=p.read_text()
assert s.count("if(storage)for(int i=0;i<9;i++)")==1
p.write_text(s.replace("if(storage)for(int i=0;i<9;i++)","if(storage)for(int i=0;i<4;i++)"))
print("SC014: four large cards, green occupied/gray empty, yellow selection, no keyboard; partitions and save engine unchanged")

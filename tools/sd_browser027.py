#!/usr/bin/env python3
"""SC027: launcher long-hold SD explorer with guarded same-volume moves."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
p=src/"main.cpp";s=p.read_text()
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
s=rep(s,'#include <sys/stat.h>','#include <sys/stat.h>\n#include <errno.h>\n#include <strings.h>')
a=s.index("static void scummTask(")
s=s[:a]+r'''
// SD explorer owns the menu only, never the running engine or save menu.
static constexpr unsigned browserPageSize=7;
struct BrowserEntry {char name[256];uint64_t bytes;bool folder;};
static BrowserEntry browserEntries[browserPageSize];
static char browserPath[512]="/sd",browserSource[512]={},browserBase[256]={};
static char browserMessage[80]={};
static bool browserActive=false,browserMore=false,browserReadOK=false;
static bool browserMoving=false,browserConfirm=false,browserDetail=false;
static bool browserHold=false,browserIgnoreRelease=false,browserTouchDown=false;
static uint32_t browserHoldStart=0;
static unsigned browserOffset=0,browserCount=0,browserDetailIndex=0;
static Point browserPoint={};
static bool browserJoin(char* out,size_t cap,const char* parent,const char* name){
    if(!name||!name[0]||!strcmp(name,".")||!strcmp(name,"..")||strchr(name,'/')||strchr(name,'\\'))return false;
    int n=snprintf(out,cap,"%s/%s",parent,name);
    return n>0&&size_t(n)<cap;
}
static void browserMsg(const char* msg){
    snprintf(browserMessage,sizeof(browserMessage),"%s",msg);
    Serial.printf("SD BROWSER %s\n",msg);
}
static void browserRead(){
    browserCount=0;browserMore=false;browserReadOK=false;
    if(!sdMounted)return;
    DIR* d=opendir(browserPath);if(!d){browserMsg("ERROR AL ABRIR CARPETA");return;}
    browserReadOK=true;
    unsigned seen=0;
    while(auto* e=readdir(d)){
        if(!strcmp(e->d_name,".")||!strcmp(e->d_name,".."))continue;
        if(strlen(e->d_name)>=sizeof(browserEntries[0].name))continue;
        char path[512];if(!browserJoin(path,sizeof(path),browserPath,e->d_name))continue;
        struct stat st;if(stat(path,&st))continue;
        if(!S_ISREG(st.st_mode)&&!S_ISDIR(st.st_mode))continue;
        if(seen++<browserOffset)continue;
        if(browserCount==browserPageSize){browserMore=true;break;}
        auto& v=browserEntries[browserCount++];
        snprintf(v.name,sizeof(v.name),"%s",e->d_name);v.folder=S_ISDIR(st.st_mode);v.bytes=st.st_size;
    }
    closedir(d);
    Serial.printf("SD BROWSE %s offset=%u entries=%u more=%u\n",browserPath,browserOffset,browserCount,browserMore);
}
static bool browserProtected(const char* path){
    // Keep the agreed platform roots and legacy ROM root intact.
    const char* roots[]={"/sd","/sd/XT","/sd/386DX","/sd/486DX4","/sd/SCUMMVM","/sd/roms","/sd/roms/scummvm"};
    for(const char* r:roots)if(!strcasecmp(path,r))return true;
    return false;
}
static bool browserWithin(const char* path,const char* parent){
    size_t len=strlen(parent);
    return !strncasecmp(path,parent,len)&&(path[len]==0||path[len]=='/');
}
static void browserShort(char* out,size_t cap,const char* name,unsigned maxChars){
    size_t n=strlen(name);
    if(n<=maxChars){snprintf(out,cap,"%s",name);return;}
    snprintf(out,cap,"%.*s...",int(maxChars-3),name);
}
static void browserDraw(){
    auto& d=ui();const auto& t=RetroUI::themes[0];d.fillScreen(BG);
    RetroUI::center(d,240,18,"SD",3,0xffff);
    RetroUI::button(d,8,36,86,36,"SALIR",t);
    RetroUI::button(d,100,36,90,36,"SUBIR",t);
    RetroUI::button(d,196,36,112,36,"RELEER",t);
    if(browserMoving)RetroUI::button(d,314,36,158,36,"CANCELAR",t);
    else{
        char cap[32];snprintf(cap,sizeof(cap),"%llu MB",(unsigned long long)(sdMounted?SD.cardSize()/1048576ULL:0));
        RetroUI::center(d,392,54,cap,1,0x9cfa);
    }
    char line[76];browserShort(line,sizeof(line),browserPath+3,72);
    RetroUI::text(d,8,83,line[0]?line:"/",1,0x5e9e);
    if(browserConfirm){
        RetroUI::center(d,240,135,"CONFIRMAR MOVIMIENTO",2,0xffff);
        browserShort(line,sizeof(line),browserBase,72);
        RetroUI::center(d,240,184,line,1,0xffff);
        RetroUI::center(d,240,218,"DESTINO",2,0x5e9e);
        browserShort(line,sizeof(line),browserPath+3,72);
        RetroUI::center(d,240,248,line[0]?line:"/",1,0xffff);
        RetroUI::center(d,240,292,"NO SE SOBRESCRIBEN ARCHIVOS",1,0x9cfa);
        RetroUI::button(d,16,340,216,60,"VOLVER",t);
        RetroUI::button(d,248,340,216,60,"CONFIRMAR",t,true);
    }else if(browserDetail&&browserDetailIndex<browserCount){
        const auto& v=browserEntries[browserDetailIndex];
        RetroUI::center(d,240,140,v.folder?"CARPETA":"ARCHIVO",2,0x5e9e);
        for(unsigned i=0;i<4&&i*72<strlen(v.name);i++){
            snprintf(line,sizeof(line),"%.72s",v.name+i*72);
            RetroUI::center(d,240,181+i*20,line,1,0xffff);
        }
        if(!v.folder){
            snprintf(line,sizeof(line),"%llu BYTES",(unsigned long long)v.bytes);
            RetroUI::center(d,240,280,line,2,0x9cfa);
        }
        RetroUI::button(d,16,340,216,60,"VOLVER",t);
        RetroUI::button(d,248,340,216,60,"MOVER",t,true);
    }else{
        if(!sdMounted)RetroUI::center(d,240,210,"SD NO MONTADA",2,0xfbe0);
        else if(!browserReadOK)RetroUI::center(d,240,210,"ERROR DE LECTURA",2,0xfbe0);
        else if(!browserCount)RetroUI::center(d,240,210,"CARPETA VACIA",2,0x9cfa);
        for(unsigned i=0;i<browserCount;i++){
            const auto& v=browserEntries[i];int y=106+i*42;
            d.fillRoundRect(8,y,464,39,4,0x2124);
            RetroUI::text(d,14,y+5,v.folder?"DIR":"ZIP/FILE",1,v.folder?0xffe0:0x5e9e);
            if(!v.folder){
                snprintf(line,sizeof(line),"%llu KB",(unsigned long long)(v.bytes/1024));
                RetroUI::text(d,85,y+5,line,1,0x9cfa);
            }
            browserShort(line,sizeof(line),v.name,browserMoving?73:61);
            RetroUI::text(d,14,y+20,line,1,0xffff);
            if(!browserMoving)RetroUI::button(d,403,y+2,65,35,"SEL",t);
        }
        if(browserMoving){
            browserShort(line,sizeof(line),browserBase,42);
            RetroUI::text(d,8,403,line,1,0xffe0);
        }else if(browserMessage[0])RetroUI::text(d,8,403,browserMessage,1,0xffe0);
        RetroUI::button(d,8,430,88,42,"<",t);
        RetroUI::button(d,102,430,88,42,">",t);
        if(browserMoving)RetroUI::button(d,202,430,270,42,"MOVER AQUI",t,true);
        else{
            snprintf(line,sizeof(line),"%u-%u%s",browserCount?browserOffset+1:0,browserOffset+browserCount,browserMore?"+":"");
            RetroUI::center(d,332,451,line,2,0x9cfa);
        }
    }
    if((browserConfirm||browserDetail)&&browserMessage[0])RetroUI::center(d,240,423,browserMessage,1,0xffe0);
    showUI();
}
static void browserResetMove(){
    browserMoving=browserConfirm=browserDetail=false;browserSource[0]=browserBase[0]=0;
}
static void browserOpen(){
    scanSD(false);
    snprintf(browserPath,sizeof(browserPath),"/sd");browserOffset=0;
    browserMessage[0]=0;browserResetMove();browserActive=true;
    browserIgnoreRelease=true;browserTouchDown=false;wasDown=false;
    browserRead();browserDraw();
}
static void browserClose(){
    browserActive=false;browserResetMove();browserHold=false;wasDown=false;
    // Return to home so the next platform entry rescans the changed directory.
    homeUI();
}
static void browserUp(){
    if(strcmp(browserPath,"/sd")){
        char* slash=strrchr(browserPath,'/');
        if(slash&&slash>browserPath+2)*slash=0;
    }
    browserOffset=0;browserMessage[0]=0;browserRead();
}
static void browserEnter(unsigned idx){
    if(idx>=browserCount||!browserEntries[idx].folder)return;
    char next[512];if(!browserJoin(next,sizeof(next),browserPath,browserEntries[idx].name)){
        browserMsg("RUTA DEMASIADO LARGA");return;
    }
    snprintf(browserPath,sizeof(browserPath),"%s",next);browserOffset=0;browserMessage[0]=0;browserRead();
}
static void browserSelect(unsigned idx){
    if(idx>=browserCount)return;
    char path[512];const auto& v=browserEntries[idx];
    if(!browserJoin(path,sizeof(path),browserPath,v.name)||browserProtected(path)){
        browserMsg("CARPETA DE SISTEMA PROTEGIDA");return;
    }
    snprintf(browserSource,sizeof(browserSource),"%s",path);
    snprintf(browserBase,sizeof(browserBase),"%s",v.name);
    browserMoving=true;browserDetail=false;browserMessage[0]=0;
}
static bool browserMove(){
    char dest[512];struct stat st;
    if(!sdMounted||!browserSource[0]||browserProtected(browserSource)||!browserJoin(dest,sizeof(dest),browserPath,browserBase)){
        browserMsg("DESTINO INVALIDO");return false;
    }
    if(browserWithin(browserPath,browserSource)||!strcasecmp(dest,browserSource)){
        browserMsg("DESTINO IGUAL O DENTRO DEL ORIGEN");return false;
    }
    if(stat(browserSource,&st)){browserMsg("ORIGEN NO DISPONIBLE");return false;}
    if(stat(browserPath,&st)||!S_ISDIR(st.st_mode)){browserMsg("CARPETA DESTINO NO DISPONIBLE");return false;}
    errno=0;
    if(!stat(dest,&st)){browserMsg("YA EXISTE / NO SE SOBRESCRIBE");return false;}
    if(errno!=ENOENT){browserMsg("NO SE PUDO VERIFICAR DESTINO");return false;}
    // Same mounted FAT volume, no copy/delete fallback. Refuse overwrite.
    if(rename(browserSource,dest)){
        Serial.printf("SD MOVE FAIL errno=%d src=%s dest=%s\n",errno,browserSource,dest);
        browserMsg("ERROR AL MOVER / REVISAR SD");return false;
    }
    Serial.printf("SD MOVE OK %s -> %s\n",browserSource,dest);
    browserResetMove();browserOffset=0;browserMsg("MOVIDO CORRECTAMENTE");browserRead();
    return true;
}
static void browserClick(Point p){
    if(browserConfirm){
        if(hit(p,16,340,216,60)){browserConfirm=false;browserMessage[0]=0;}
        else if(hit(p,248,340,216,60)){browserMove();}
        browserDraw();return;
    }
    if(hit(p,8,36,86,36)){browserClose();return;}
    if(browserDetail){
        if(hit(p,16,340,216,60)){browserDetail=false;browserMessage[0]=0;}
        else if(hit(p,248,340,216,60))browserSelect(browserDetailIndex);
        browserDraw();return;
    }
    if(hit(p,100,36,90,36))browserUp();
    else if(hit(p,196,36,112,36)){
        if(!sdMounted){scanSD(false);snprintf(browserPath,sizeof(browserPath),"/sd");browserOffset=0;}
        browserMessage[0]=0;browserRead();
    }else if(browserMoving&&hit(p,314,36,158,36)){browserResetMove();browserMessage[0]=0;}
    else if(hit(p,8,430,88,42)&&browserOffset>=browserPageSize){browserOffset-=browserPageSize;browserRead();}
    else if(hit(p,102,430,88,42)&&browserMore){browserOffset+=browserPageSize;browserRead();}
    else if(browserMoving&&hit(p,202,430,270,42)){browserConfirm=true;browserMessage[0]=0;}
    else if(p.y>=106&&p.y<106+browserPageSize*42){
        unsigned i=(p.y-106)/42;
        if(i<browserCount){
            if(!browserMoving&&p.x>=403)browserSelect(i);
            else if(browserEntries[i].folder)browserEnter(i);
            else if(!browserMoving){browserDetailIndex=i;browserDetail=true;browserMessage[0]=0;}
        }
    }
    browserDraw();
}
static bool browserTick(){
    if(browserActive){
        if(browserIgnoreRelease){if(!npoints)browserIgnoreRelease=false;return true;}
        if(npoints==1&&!browserTouchDown){browserPoint=points[0];browserTouchDown=true;}
        else if(npoints>1){browserTouchDown=false;browserIgnoreRelease=true;}
        else if(!npoints&&browserTouchDown){
            browserTouchDown=false;browserClick(browserPoint);
        }
        return true;
    }
    // Hold must stay within the corner, with exactly one finger for 5000 ms.
    const bool corner=npoints==1&&points[0].x<64&&points[0].y>=416;
    if(!corner){browserHold=false;return false;}
    if(!browserHold){browserHold=true;browserHoldStart=millis();}
    if(uint32_t(millis()-browserHoldStart)>=5000){
        browserHold=false;browserOpen();return true;
    }
    return false;
}
'''+s[a:]
s=rep(s,'  if(npoints){if(!wasDown)gestureStart=points[0];gestureEnd=points[0];}',
'  if(browserTick()){delay(12);return;}\n  if(npoints){if(!wasDown)gestureStart=points[0];gestureEnd=points[0];}')
p.write_text(s.replace("SC026","SC027"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC026","SC027"))
print("SC027: SD explorer long hold 5000ms, paginated files and folders, explicit same-volume move, no overwrite or protected root moves")

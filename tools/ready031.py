#!/usr/bin/env python3
"""SC031: preboot original shared DOS disk; safe per-game boot for separate folders.
Show real milestone progress, expose guest on failure, never claim a game ran
merely because the CPU or DOS prompt initialized.
"""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"dos_runtime.cpp";s=p.read_text()
s=rep(s,'#include "legacy_disk030.h"','#include "legacy_disk030.h"\nstatic bool folderBootPending=false,folderGamePending=false,folderCarmen=false,folderPromptGone=false,classicBootPending=false;\nstatic uint32_t folderBootAt=0,folderGameAt=0,classicBootAt=0;\nstatic char folderCommand[13]={};\nbool dos_classic_available(const char* path){LegacyHeader h{};uint32_t base=0;return legacyHeader(path,base,h);}')
s=rep(s,'void dos_touch_game(unsigned n,int x,int y){','void dos_touch_game(unsigned n,int x,int y){\n if(folderBootPending||folderGamePending||classicBootPending)return;')
s=rep(s,' showLoading(-1);\n Serial.printf("DOS ENTRY',r''' host.video.drain();__atomic_store_n(&hideGuest,true,__ATOMIC_RELAXED);
 loadStage=0;
 dosLcd->fillScreen(0);
 centered("PRISMA DOS",28,3,0x9cfa);
 const char* name=strrchr(path,'/');name=name?name+1:path;
 char displayName[37];snprintf(displayName,sizeof(displayName),"%.36s",name);
 centered(displayName,260,2);
 if(DosArt::large[3])dosLcd->draw16bitRGBBitmap(96,66,const_cast<uint16_t*>(DosArt::large[3]),288,180);
 loadProgress(10,"Validando origen SD");
 Serial.printf("DOS ENTRY''')
s=rep(s,'  bool floppy=true,classic=false;', '  bool floppy=true,classic=false;\n  loadProgress(20,"Origen encontrado");')
s=rep(s,'    auto* a=new LegacyDisk(path,base+h.floppyOffset,h.floppySize);','    loadProgress(30,"Disquete A: original");\n    auto* a=new LegacyDisk(path,base+h.floppyOffset,h.floppySize);')
s=rep(s,'    auto* c=new LegacyDisk(path,base+h.hardOffset,h.hardSize);','    loadProgress(40,"Disco C: original");\n    auto* c=new LegacyDisk(path,base+h.hardOffset,h.hardSize);')
s=rep(s,'    auto* folder=new FolderDisk(path);','    loadProgress(30,"Preparando disco C:");\n    auto* folder=new FolderDisk(path);')
s=rep(s,'    cfg.diskDriveC=folder;',r'''    cfg.diskDriveC=folder;
    snprintf(folderCommand,sizeof(folderCommand),"%s",folder->launchCommand());
    folderCarmen=folder->isCarmen();
    folderBootPending=true;
    folderBootAt=millis();
    loadProgress(45,"FreeDOS A: y C: listos");''')
s=rep(s,'  cfg.singleThreaded=true;','  loadProgress(50,"Configurando Faux86");\n  cfg.singleThreaded=true;')
s=rep(s,'  vga_framebuffer=(uint16_t*)ps_calloc','  loadProgress(60,"Memoria y video");\n  vga_framebuffer=(uint16_t*)ps_calloc')
s=rep(s,'  vm=new Faux86::VM(cfg);','  loadProgress(65,"Inicializando maquina");\n  vm=new Faux86::VM(cfg);')
s=rep(s,'    loadProgress(35,"DOS clasico / 071");','    classicBootPending=true;classicBootAt=millis();\n    loadProgress(70,"MS-DOS clasico / 071");')
s=rep(s,'''  __atomic_store_n(&hideGuest,false,__ATOMIC_RELAXED);
  host.video.invalidate();vm->video.updatedscreen=true;
  setPanel(1);''',r'''  if(folderBootPending){
    loadProgress(70,"Iniciando FreeDOS");
  }else{
    // Standalone image may boot any OS: only claim VM readiness.
    loadProgress(100,"Maquina virtual lista");
    __atomic_store_n(&hideGuest,false,__ATOMIC_RELAXED);
    host.video.invalidate();vm->video.updatedscreen=true;
    setPanel(1);
  }''')
s=rep(s,'   promptCheck=millis();bool prompt=atPrompt();',r'''   promptCheck=millis();bool prompt=atPrompt();
   if(classicBootPending){
     if(prompt){
       classicBootPending=false;
       Serial.printf("SC031 CLASSIC DOS READY ms=%u\n",millis()-classicBootAt);
     }else if(millis()-classicBootAt>45000){
       classicBootPending=false;bootPhase=false;consoleMode=true;
       __atomic_store_n(&hideGuest,false,__ATOMIC_RELAXED);
       host.video.invalidate();vm->video.updatedscreen=true;setPanel(1);
       Serial.println("SC031 CLASSIC BOOT TIMEOUT: guest exposed");
     }
   }
   if(folderBootPending){
     if(vm->cpu.didbootstrap&&loadStage<80)loadProgress(80,"Arrancando DOS");
     if(prompt){
       folderBootPending=false;
       loadProgress(90,"DOS listo");
       Serial.printf("SC031 FOLDER DOS READY ms=%u\n",millis()-folderBootAt);
       bool ok=folderCommand[0]!=0&&!textCount;
       if(ok){
         for(const char* c=folderCommand;*c;c++)if(!textChar(*c)){ok=false;break;}
         if(ok)ok=textChar(13);
       }
       if(ok){
         activeGame=folderCarmen?0:-1;
         vm->cpu.prismaMouseEnabled=folderCarmen;
         vm->cpu.prismaMousePending=false;
         folderGamePending=true;folderPromptGone=false;folderGameAt=millis();
         loadProgress(95,"Ejecutando programa");
         Serial.printf("SC031 DOS AUTO EXEC %s profile=%d\n",folderCommand,activeGame);
       }else{
         clearText();loadProgress(100,"DOS listo / consola");
         __atomic_store_n(&hideGuest,false,__ATOMIC_RELAXED);
         host.video.invalidate();vm->video.updatedscreen=true;setPanel(1);
         Serial.println("SC031 no unique executable: console");
       }
     }else if(millis()-folderBootAt>45000){
       folderBootPending=false;
       __atomic_store_n(&hideGuest,false,__ATOMIC_RELAXED);
       host.video.invalidate();vm->video.updatedscreen=true;setPanel(1);
       Serial.println("SC031 FOLDER BOOT TIMEOUT: guest exposed");
     }
   }
   if(folderGamePending){
     if(!prompt)folderPromptGone=true;
     unsigned mode=vm->memory.readByte(0x449)&0x7f;
     bool graphics=folderPromptGone&&mode>3&&mode!=7;
     bool backAtPrompt=folderPromptGone&&prompt&&millis()-folderGameAt>1500;
     bool timeout=millis()-folderGameAt>20000;
     if(graphics||backAtPrompt||timeout){
       folderGamePending=false;
       if(graphics)loadProgress(100,"Video del juego listo");
       else if(backAtPrompt)Serial.println("SC031 AUTO EXEC returned to DOS");
       else Serial.println("SC031 AUTO EXEC timeout: guest exposed");
       logGuestText();
       __atomic_store_n(&hideGuest,false,__ATOMIC_RELAXED);
       host.video.invalidate();vm->video.updatedscreen=true;
       vm->video.prismaDrawDue=true;
       setPanel(graphics?0:1);
     }
   }''')
s=rep(s,'   if(bootPhase||loadingGame)logGuestText();','   if(bootPhase||loadingGame||folderBootPending||folderGamePending)logGuestText();')
s=rep(s,'       loadingGame=false;host.video.invalidate();','       if(!prompt&&mode>3&&mode!=7)loadProgress(100,"Video del juego listo");\n       loadingGame=false;host.video.invalidate();')
p.write_text(s.replace("SC030","SC031"))
p=src/"main.cpp";s=p.read_text()
s=rep(s,'bool dos_start_image(Arduino_RGB_Display&,const char*);','bool dos_start_image(Arduino_RGB_Display&,const char*);\nbool dos_classic_available(const char*);')
s=rep(s,'static void drawDosCarousel(){',r'''static bool prebootClassicIfShared(){
    // A single shared classic image contains its own two-game launcher.
    // Mixed catalogs remain selectable, so the classic route cannot hide SD games.
    if(dosCount!=1||dosEntries[0].kind!=5)return false;
    char path[192];int n=snprintf(path,sizeof(path),"%s/%s",dosRoots[dosProfile],dosEntries[0].name);
    if(n<0||n>=int(sizeof(path))||!dos_classic_available(path))return false;
    Serial.printf("SC031 CLASSIC PREBOOT profile=%d %s\n",dosProfile,path);
    startDosImage();return true;
}
static void drawDosCarousel(){''')
s=rep(s,'else{scanDosLibrary(i-1);drawDosCarousel();}',
      'else{scanDosLibrary(i-1);if(!prebootClassicIfShared())drawDosCarousel();}')
s=rep(s,'item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / FREEDOS"','item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / CARGA AUTO"')
s=rep(s,'      pollTouch();\n      if(!dos_launcher_touch',r'''      static uint32_t lastDosTouch=0;
      if(millis()-lastDosTouch>=12){
      lastDosTouch=millis();pollTouch();
      if(!dos_launcher_touch''')
s=rep(s,'          dos_touch_game(npoints,npoints?points[0].x:0,npoints?points[0].y:0);\n      dos_tick();return;', '          dos_touch_game(npoints,npoints?points[0].x:0,npoints?points[0].y:0);\n      }\n      dos_tick();return;')
p.write_text(s.replace("SC030-CLASSIC","SC031-DOS").replace("SC030","SC031"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC030","SC031"))
print("SC031: verified shared classic preboot, per-folder auto boot, real loading milestones")

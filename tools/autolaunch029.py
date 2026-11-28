#!/usr/bin/env python3
"""Restore 071's automatic command injection and Carmen touch profile.
No proprietary game/OS bytes in source; do not write the user's SD.
"""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"dos_runtime.cpp";s=p.read_text()
s=rep(s,'#include "folder_disk027.h"','#include "folder_disk027.h"\nstatic char folderCommand[13]={};\nstatic bool folderCarmen=false,folderLaunchPending=false;\nstatic uint32_t folderBootAt=0;')
s=rep(s,'    cfg.diskDriveC=folder;','''    cfg.diskDriveC=folder;
    snprintf(folderCommand,sizeof(folderCommand),"%s",folder->launchCommand());
    folderCarmen=folder->isCarmen();
    folderLaunchPending=folderCommand[0]!=0;
    folderBootAt=millis();''')
# Generic console remains available if no unambiguous executable.
# Use the verified BIOS keyboard queue, not simulated touch keypresses.
s=rep(s,'   promptCheck=millis();bool prompt=atPrompt();',r'''   promptCheck=millis();bool prompt=atPrompt();
   if(folderLaunchPending&&prompt&&!textCount){
     folderLaunchPending=false;
     bool ok=true;
     for(const char* c=folderCommand;*c;c++)if(!textChar(*c)){ok=false;break;}
     if(ok)ok=textChar(13);
     if(ok){
       activeGame=folderCarmen?0:-1;
       consoleMode=true;mouseMode=true;
       vm->cpu.prismaMouseEnabled=folderCarmen;
       vm->cpu.prismaMousePending=false;
       setPanel(0);
       launchTime=millis();
       Serial.printf("SC029 DOS AUTO EXEC %s profile=%d boot_ms=%u\n",folderCommand,activeGame,millis()-folderBootAt);
       logGuestText();
     }else{clearText();Serial.println("SC029 DOS AUTO EXEC queue failed");}
   }else if(folderLaunchPending&&millis()-folderBootAt>30000){
     folderLaunchPending=false;Serial.println("SC029 DOS AUTO EXEC prompt timeout");
   }''')
# Keep console visible if execution fails, without trapping the user in a reboot.
# Preserve diagnostic capture of guest error messages around launch.
s=rep(s,'   if(bootPhase||loadingGame)logGuestText();','   if(bootPhase||loadingGame||(launchTime&&millis()-launchTime<15000))logGuestText();')
s=s.replace("SC028","SC029")
p.write_text(s)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'      pollTouch();\n      dos_touch_game(npoints,npoints?points[0].x:0,npoints?points[0].y:0);',
r'''      static uint32_t lastDosTouch=0;
      if(millis()-lastDosTouch>=12){
          lastDosTouch=millis();pollTouch();
          dos_touch_game(npoints,npoints?points[0].x:0,npoints?points[0].y:0);
      }''')
s=rep(s,'item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / FREEDOS"','item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / INICIO AUTO"')
s=rep(s,'dosCount?"ABRIR":"RELEER"','dosCount?"JUGAR":"RELEER"')
p.write_text(s.replace("SC028","SC029"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC028","SC029"))
print("SC029: boot to actual executable, restore Carmen controls, no SD writes, throttle touch polling")

#!/usr/bin/env python3
"""SC030-CLASSIC: exact original 071 DOS boot/launcher using user-owned PRDOS032 disks.
Keep SCUMMVM and generic folder path from hardware-boot-tested SC028. No SD writes.
"""
from pathlib import Path
import sys,shutil
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
shutil.copyfile(Path(__file__).with_name("legacy_disk030.h"),src/"legacy_disk030.h")
p=src/"dos_runtime.cpp";s=p.read_text()
s=rep(s,'#include "folder_disk027.h"','#include "folder_disk027.h"\n#include "legacy_disk030.h"')
s=rep(s,'  bool floppy=true;\n  if(S_ISDIR(st.st_mode)){',r'''  bool floppy=true,classic=false;
  const char* ext=strrchr(path,'.');
  if(S_ISREG(st.st_mode)&&ext&&!strcasecmp(ext,".bin")){
    LegacyHeader h{};uint32_t base=0;
    if(!legacyHeader(path,base,h)){fail("BIN sin discos PRDOS032");return false;}
    auto* a=new LegacyDisk(path,base+h.floppyOffset,h.floppySize);
    auto* c=new LegacyDisk(path,base+h.hardOffset,h.hardSize);
    if(!a->isValid()||!c->isValid()){delete a;delete c;fail("Error discos DOS clasicos");return false;}
    cfg.diskDriveA=a;cfg.diskDriveC=c;classic=true;
    Serial.printf("SC030 CLASSIC 071 BOOT PRDOS032 base=%u A=%u C=%u\n",base,h.floppySize,h.hardSize);
  }else if(S_ISDIR(st.st_mode)){''')
# Keep original 071 initialization and prompt-driven launcher; do not enter
# generic console on the classic route. Old DOS clock, touch profiles, mouse
# hacks and original startup scripts are untouched.
s=rep(s,'  host.init(vm);\n  // Show the guest from the first BIOS frame.',r'''  host.init(vm);
  if(classic){
    loadProgress(35,"DOS clasico / 071");
    last=millis();lastInstructions=vm->cpu.totalexec;
    Serial.println("SC030 CLASSIC 071 VM READY");
    return true;
  }
  // Show the guest from the first BIOS frame.''')
p.write_text(s.replace("SC028","SC030"))
p=src/"main.cpp";s=p.read_text()
s=rep(s,'    if(!strcasecmp(ext,".img")||!strcasecmp(ext,".ima"))return 4;',
r'''    if(!strcasecmp(ext,".img")||!strcasecmp(ext,".ima"))return 4;
    if(!strcasecmp(ext,".bin")&&(!strncasecmp(name,"PRISMA-",7)||!strcasecmp(name,"dosdata.bin")))return 5;''')
s=rep(s,'case 4:return "IMAGEN DE DISCO";','case 4:return "IMAGEN DE DISCO";case 5:return "DOS CLASICO 071";')
s=rep(s,'item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / FREEDOS"',
      'item.kind==5?"PRDOS032 / MOTOR 071":item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / FREEDOS"')
s=rep(s,'void dos_touch_game(unsigned,int,int);','void dos_touch_game(unsigned,int,int);\nbool dos_launcher_touch(unsigned,int,int);')
s=rep(s,'      dos_touch_game(npoints,npoints?points[0].x:0,npoints?points[0].y:0);',
r'''      if(!dos_launcher_touch(npoints,npoints?points[0].x:0,npoints?points[0].y:0))
          dos_touch_game(npoints,npoints?points[0].x:0,npoints?points[0].y:0);''')
s=rep(s,'dosCount?"ABRIR":"RELEER"','dosCount?"JUGAR":"RELEER"')
p.write_text(s.replace("SC028-DOS","SC030-CLASSIC").replace("SC028","SC030"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC028","SC030"))
print("SC030: original 071 launcher and original boot disks from SD; generic folders stay separate")

#!/usr/bin/env python3
"""SC027: boot FreeDOS from flash; expose the chosen directory as C:."""
from pathlib import Path
import sys,shutil
root=Path(sys.argv[1]).resolve()
src=root/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
shutil.copyfile(Path(__file__).with_name("folder_disk027.h"),src/"folder_disk027.h")
p=src/"dos_runtime.cpp";s=p.read_text()
s=rep(s,'class FlashDisk final', '#include "folder_disk027.h"\n#include "freedos_boot027.h"\nclass FlashDisk final')
s=rep(s,'  auto* disk=new SDDisk(path);\n  if(!disk->isValid()){delete disk;fail("Invalid SD disk image");return false;}\n  const bool floppy=disk->floppy();\n  if(floppy)cfg.diskDriveA=disk;else cfg.diskDriveC=disk;\n  Serial.printf("SC026 DOS SD image=%s bytes=%llu type=%s readonly\\n",path,(unsigned long long)disk->getSize(),floppy?"floppy":"hard disk");',r'''  struct stat st;
  if(stat(path,&st)!=0){fail("SD path unavailable");return false;}
  bool floppy=true;
  if(S_ISDIR(st.st_mode)){
    auto* folder=new FolderDisk(path);
    if(!folder->isValid()){delete folder;fail("Unsupported DOS folder");return false;}
    cfg.diskDriveA=new FlashROM(prismaFreeDOSBoot,sizeof(prismaFreeDOSBoot));
    cfg.diskDriveC=folder;
    Serial.printf("SC027 DOS folder C: %s; FreeDOS A: flash\n",path);
  }else{
    auto* disk=new SDDisk(path);
    if(!disk->isValid()){delete disk;fail("Invalid SD disk image");return false;}
    floppy=disk->floppy();
    if(floppy)cfg.diskDriveA=disk;else cfg.diskDriveC=disk;
    Serial.printf("SC027 DOS image %s bytes=%llu\n",path,(unsigned long long)disk->getSize());
  }''')
p.write_text(s.replace("SC026","SC027"))
p=src/"main.cpp";s=p.read_text()
s=rep(s,"if(!dosCount||dosEntries[dosIndex].kind!=4)return;","if(!dosCount)return;")
s=rep(s,'"IMAGEN ARRANCABLE / SOLO LECTURA":"CARPETA / CARGA PENDIENTE"','"IMAGEN / SOLO LECTURA":"CARPETA / FREEDOS"')
s=rep(s,'dosCount&&dosEntries[dosIndex].kind==4?"ABRIR":"RELEER"','dosCount?"ABRIR":"RELEER"')
s=rep(s,'if(dosCount&&dosEntries[dosIndex].kind==4)startDosImage();','if(dosCount)startDosImage();')
p.write_text(s.replace("SC026","SC027"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC026","SC027"))
print("SC027: mount chosen directory as read-only C:, flash boot A:, no automatic game command")

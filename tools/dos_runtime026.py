#!/usr/bin/env python3
"""SC026: link original optimized XT runtime beside native SCUMMVM.
First launch gate is a read-only bootable disk image. Folder-to-DOS bridge follows.
No change to partitions, ScummVM renderer, game files or saves.
"""
from pathlib import Path
import sys,subprocess,textwrap
root=Path(sys.argv[1]).resolve()
src=root/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
def original(path):
    return subprocess.check_output(["git","-C",str(root),"show","HEAD:firmware/s3-4848-retro/"+path]).decode()
for name in ("dos_runtime.cpp","prisma_diag.cpp","prisma_diag.h"):
    (src/name).write_text(original("src/"+name))
# Preserve all upstream 071 library patches byte for byte, substituting only env name.
workflow=subprocess.check_output(["git","-C",str(root),"show","HEAD:.github/workflows/s3-combined.yml"]).decode()
def extract_step(name):
    start=workflow.index("      - name: "+name+"\n")
    start=workflow.index("        run: |\n",start)+len("        run: |\n")
    end=workflow.index("\n      - ",start)
    return textwrap.dedent(workflow[start:end]).replace("esp32-4848s040-combined","esp32-4848s040")
(root/"tools/sc026-patch-dos.sh").write_text("set -eu\n"+extract_step("Add controlled RGB DMA shutdown for DOS restart")+"\n"+extract_step("Patch Faux86 CPU scheduling and VGA renderer")+"\n")
p=root/"platformio.ini";s=p.read_text()
line="lib_deps = moononournation/GFX Library for Arduino @ 1.6.4"
s=rep(s,line,'''lib_deps =
    moononournation/GFX Library for Arduino @ 1.6.4
    https://github.com/moononournation/Faux86-remake.git#03fe2009debd2c5fd295b131ac6afea275e1ce0f
    https://github.com/adafruit/Adafruit_Faux86.git#aa3d577a462e1000777b0155e70f81e27eea44c2
lib_ldf_mode = deep+''')
s=rep(s,"build_src_filter = -<*> +<main.cpp>","build_src_filter = -<*> +<main.cpp> +<dos_runtime.cpp> +<prisma_diag.cpp>")
p.write_text(s)
p=src/"dos_runtime.cpp";s=p.read_text()
s=rep(s,"#include <Arduino.h>","#include <Arduino.h>\n#include <stdio.h>\n#include <sys/stat.h>")
# POSIX read-only sector device; do not mount ZIP, write the SD, or infer a bootable OS.
i=s.index("class FlashDisk final")
s=s[:i]+r'''class SDDisk final : public Faux86::DiskInterface {
 FILE* file=nullptr;uint64_t len=0,pos=0;
public:
 explicit SDDisk(const char* path){
   struct stat st;
   if(stat(path,&st)!=0||!S_ISREG(st.st_mode)||st.st_size<512||st.st_size%512||st.st_size>0x7fffffff)return;
   file=fopen(path,"rb");if(file)len=st.st_size;
 }
 ~SDDisk(){if(file)fclose(file);}
 bool isValid() override{return file&&len;}
 uint64_t getSize() override{return len;}
 uint64_t seek(uint64_t off) override{pos=off>len?len:off;return pos;}
 int read(uint8_t* buf,unsigned count) override{
   if(!file||pos>=len)return 0;
   unsigned n=(unsigned)min<uint64_t>(count,len-pos);
   uint32_t start=micros();
   if(fseek(file,(long)pos,SEEK_SET)!=0)return 0;
   int got=fread(buf,1,n,file);pos+=got;++diskReads;diskReadUs+=micros()-start;
   return got;
 }
 int write(const uint8_t*,unsigned) override{return 0;}
 bool floppy() const{return len==163840||len==184320||len==327680||len==368640||len==737280||len==1228800||len==1474560||len==2949120;}
};
'''+s[i:]
s=rep(s,"bool dos_start(Arduino_RGB_Display &display){","bool dos_start_image(Arduino_RGB_Display &display,const char* path){")
a=s.index('  const auto *part=esp_partition_find_first',s.index("bool dos_start_image"))
b=s.index("  cfg.singleThreaded",a)
s=s[:a]+r'''  auto* disk=new SDDisk(path);
  if(!disk->isValid()){delete disk;fail("Invalid SD disk image");return false;}
  const bool floppy=disk->floppy();
  if(floppy)cfg.diskDriveA=disk;else cfg.diskDriveC=disk;
  Serial.printf("SC026 DOS SD image=%s bytes=%llu type=%s readonly\n",path,(unsigned long long)disk->getSize(),floppy?"floppy":"hard disk");
'''+s[b:]
s=rep(s,'  cfg.setBootDrive("fd0");','  cfg.setBootDrive(floppy?"fd0":"hd0");')
s=rep(s,'  host.init(vm);loadProgress(35,"Maquina virtual lista");last=millis();lastInstructions=vm->cpu.totalexec;Serial.println("DOS VM READY");return true;',r'''  host.init(vm);
  // Show the guest from the first BIOS frame. Disable the old two-game auto launcher
  // and all game-specific RAM cursor hacks; the user controls the DOS console.
  bootPhase=false;consoleMode=true;activeGame=-1;
  __atomic_store_n(&hideGuest,false,__ATOMIC_RELAXED);
  host.video.invalidate();vm->video.updatedscreen=true;
  setPanel(1);
  last=millis();lastInstructions=vm->cpu.totalexec;Serial.println("SC026 DOS VM READY");return true;''')
p.write_text(s)
p=src/"main.cpp";s=p.read_text()
# The old SCUMM entry retained its historical DOS name; make ownership explicit.
assert "dos_start(" in s
s=s.replace("dos_start(","scumm_start(")
s=rep(s,"static void drawDosCarousel(){",r'''bool dos_start_image(Arduino_RGB_Display&,const char*);
void dos_tick();
void dos_touch_game(unsigned,int,int);
void dos_report_reset();
bool dos_prepare_restart();
bool dos_diag_bench();
static bool dosActive=false;
void prisma_diag_status(){
    Serial.printf("SC026 DOS active=%d heap=%u psram=%u\n",dosActive,ESP.getFreeHeap(),ESP.getFreePsram());
}
bool prisma_diag_bench(){return dosActive&&dos_diag_bench();}
void dos_restart_home(){
    if(dos_prepare_restart()){
#ifdef PRISMA_RGB_SHUTDOWN
        rgb.prismaStopForReset();
#endif
    }
    Serial.flush();ESP.restart();
}
void dos_restart_to_selector(){dos_restart_home();}
static void startDosImage(){
    if(!dosCount||dosEntries[dosIndex].kind!=4)return;
    char path[192];
    int n=snprintf(path,sizeof(path),"%s/%s",dosRoots[dosProfile],dosEntries[dosIndex].name);
    if(n<0||n>=int(sizeof(path)))return;
    menuCanvas.release();
    dosActive=dos_start_image(lcd,path);
    if(!dosActive){delay(1500);ESP.restart();}
}
static void drawDosCarousel(){''')
s=rep(s,'RetroUI::center(d,240,384,"MOTOR DOS PENDIENTE",1,0xfbe0);','RetroUI::center(d,240,384,item.kind==4?"IMAGEN ARRANCABLE / SOLO LECTURA":"CARPETA / CARGA PENDIENTE",1,0xfbe0);')
s=rep(s,'RetroUI::button(d,318,436,150,32,"RELEER",t);','RetroUI::button(d,318,436,150,32,dosCount&&dosEntries[dosIndex].kind==4?"ABRIR":"RELEER",t);')
s=rep(s,'else if(hit(p,318,436,150,32)){scanDosLibrary(dosProfile);drawDosCarousel();}','else if(hit(p,318,436,150,32)){if(dosCount&&dosEntries[dosIndex].kind==4)startDosImage();else{scanDosLibrary(dosProfile);drawDosCarousel();}}')
s=rep(s,"void loop(){\n  if(runtimeActive){delay(20);return;}",r'''void loop(){
  if(dosActive){
      pollTouch();
      dos_touch_game(npoints,npoints?points[0].x:0,npoints?points[0].y:0);
      dos_tick();return;
  }
  if(runtimeActive){delay(20);return;}''')
# Avoid adding diagnostic globals ahead of native SCUMM declarations.
s=rep(s,"#include <SD.h>",'#include <SD.h>\n#include "prisma_diag.h"')
s=rep(s,"scDiagInit();","scDiagInit();diag_begin();dos_report_reset();")
p.write_text(s.replace("SC025","SC026"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC025","SC026"))
print("SC026: original 071 Faux86 runtime + pinned patches, image-only read-only launch; folder bridge pending")

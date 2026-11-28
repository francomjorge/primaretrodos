#!/usr/bin/env python3
"""SC028-DOS: disambiguate runtime from old SC027 browser; preserve four-card home.
Read-only launch from extracted directories or disk images. No ZIP decompression.
"""
from pathlib import Path
import sys,subprocess
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
commit=subprocess.check_output(["git","-C",str(Path(__file__).resolve().parent.parent),"rev-parse","--short=8","HEAD"]).decode().strip()
assert len(commit)==8 and all(c in "0123456789abcdef" for c in commit)
p=src/"main.cpp";s=p.read_text()
# Keep the physical four-card home layout from the old browser branch,
# but route each card to the actual runtime-enabled catalog.
a=s.index("static void homeUI(){")
b=s.index("\n}",a)+2
assert 'SC027 / BIBLIOTECAS SD' in s[a:b]
s=s[:a]+r'''static void homeUI(){
    selected=false;dosProfile=-1;
    auto& d=ui();
    d.fillScreen(BG);
    RetroUI::center(d,240,24,"PRISMA RETRO",3,0xffff);
    RetroUI::center(d,240,55,"SC028-DOS / BUILD_ID",1,0x9cfa);
    const char* names[]={"SCUMMVM","XT","386DX","486DX4"};
    const char* subtitle[]={"MOTOR NATIVO / DEMO FLASH","DOS / FAUX86","DOS / FAUX86","DOS / FAUX86"};
    for(int i=0;i<4;i++){
        int x=12+(i%2)*234,y=78+(i/2)*194;
        d.fillRoundRect(x,y,222,182,8,0x2124);
        d.drawRoundRect(x,y,222,182,8,0x5e9e);
        RetroUI::console(d,x+59,y+12,3,0);
        RetroUI::center(d,x+111,y+119,names[i],2,0xffff);
        RetroUI::center(d,x+111,y+147,subtitle[i],1,0x9cfa);
    }
    showUI();
}'''.replace("BUILD_ID",commit)+s[b:]
a=s.index('if(!selected&&hit(p,16,82,448,58))')
b=s.index('else if(selected&&dosProfile>=0)',a)
s=s[:a]+r'''if(!selected){
          for(int i=0;i<4;i++){
              int x=12+(i%2)*234,y=78+(i/2)*194;
              if(!hit(p,x,y,222,182))continue;
              if(i==0){dosProfile=-1;scanSD();drawScummCarousel();}
              else{scanDosLibrary(i-1);drawDosCarousel();}
              break;
          }
      }
      '''+s[b:]
# Archive entries remain unexecuted. Explain exactly why, instead of falsely
# implying the DOS engine is missing. No ZIP code or filesystem writes.
s=rep(s,'static unsigned dosCount=0,dosIndex=0,dosSkipped=0;',
      'static unsigned dosCount=0,dosIndex=0,dosSkipped=0,dosArchives=0;')
s=rep(s,'dosProfile=profile;dosCount=0;dosIndex=0;dosSkipped=0;',
      'dosProfile=profile;dosCount=0;dosIndex=0;dosSkipped=0;dosArchives=0;')
s=rep(s,'        if(!kind){dosSkipped++;continue;}',
r'''        if(!kind){
            const char* ext=strrchr(n,'.');
            if(ext&&(!strcasecmp(ext,".zip")||!strcasecmp(ext,".7z")))dosArchives++;
            else dosSkipped++;
            continue;
        }''')
s=rep(s,'!dosDirectoryFound?"CARPETA NO EXISTE":"SIN JUEGOS"',
      '!dosDirectoryFound?"CARPETA NO EXISTE":dosArchives?"DESCOMPRIMIR ZIP":"SIN JUEGOS"')
s=rep(s,'    snprintf(line,sizeof(line),"OMITIDOS: %u",dosSkipped);',
      '    snprintf(line,sizeof(line),"ZIP: %u / OTROS: %u",dosArchives,dosSkipped);')
s=rep(s,'    RetroUI::text(d,114,10,dosNames[dosProfile],2,0xffff);',
      '    RetroUI::text(d,114,10,dosNames[dosProfile],2,0xffff);\n    RetroUI::text(d,114,54,"SC028-DOS",1,0x07e0);')
s=rep(s,'item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / FREEDOS"',
      'item.kind==4?"IMAGEN / SOLO LECTURA":"CARPETA / FREEDOS"') if False else s
# Support both existing SCUMM paths (the old SD-browser branch did too).
s=rep(s,'char folder[64],id[24];','char folder[64],id[24],path[160];')
s=rep(s,'static void scanSD(){\n    sdCount=0;sdSkipped=0;sdTruncated=false;catalogIndex=0;\n    if(!mountLibrarySD())return;\n    DIR* dir=opendir("/sd/roms/scummvm");',
      'static void scanSCUMMRoot(const char* root){\n    DIR* dir=opendir(root);')
s=rep(s,'char path[160];snprintf(path,sizeof(path),"/sd/roms/scummvm/%s",n);',
      'char path[160];snprintf(path,sizeof(path),"%s/%s",root,n);')
s=rep(s,'        if(sdCount==maxSDGames){sdTruncated=true;break;}',
r'''        bool duplicate=false;
        for(unsigned i=0;i<sdCount;i++)if(!strcasecmp(sdGames[i].folder,n)){duplicate=true;break;}
        if(duplicate)continue;
        if(sdCount==maxSDGames){sdTruncated=true;break;}''')
s=rep(s,'        sdCount++;\n    }\n    closedir(dir);\n    for(unsigned i=1;i<sdCount;i++){',
r'''        snprintf(sdGames[sdCount].path,sizeof(sdGames[0].path),"%s",path);
        sdCount++;
        delay(1);
    }
    closedir(dir);
}
static void scanSD(){
    sdCount=0;sdSkipped=0;sdTruncated=false;catalogIndex=0;
    if(!mountLibrarySD())return;
    scanSCUMMRoot("/sd/SCUMMVM");
    scanSCUMMRoot("/sd/roms/scummvm");
    for(unsigned i=1;i<sdCount;i++){''')
s=rep(s,'snprintf(path,256,"/sd/roms/scummvm/%s",name);',
      'snprintf(path,256,"%s",sdGames[catalogIndex-1].path);')
# Restore known working SD clock, retry slower on error; no format.
s=rep(s,'        sdMounted=SD.begin(42,SPI,10000000,"/sd",10,false);',
r'''        const uint32_t clocks[]={4000000,400000};
        for(uint32_t hz:clocks){
            sdMounted=SD.begin(42,SPI,hz,"/sd",10,false);
            Serial.printf("SC028 SD hz=%lu mounted=%d\n",(unsigned long)hz,sdMounted);
            if(sdMounted)break;
            SD.end();digitalWrite(42,HIGH);delay(20);
        }''')
s=rep(s,'scDiagInit();diag_begin();dos_report_reset();',
      'scDiagInit();diag_begin();dos_report_reset();Serial.println("SC028-DOS BUILD '+commit+'");')
s=s.replace("SC027","SC028")
p.write_text(s)
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC027","SC028"))
p=src/"dos_runtime.cpp";p.write_text(p.read_text().replace("SC027","SC028"))
print("SC028-DOS identity",commit,"four-card home, real DOS launch, dual SCUMM paths, archives excluded")

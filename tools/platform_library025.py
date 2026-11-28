#!/usr/bin/env python3
"""SC025: independent SD catalogs; no DOS runtime or archive extraction yet."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
# Reuse the exact board mount from SC024.
s=rep(s,"static void scanSD(){\n    sdCount=0;sdSkipped=0;sdTruncated=false;catalogIndex=0;", "static bool mountLibrarySD(){")
s=rep(s,'    if(!sdMounted)return;\n    DIR* dir=opendir("/sd/roms/scummvm");', '''    return sdMounted;
}
static void scanSD(){
    sdCount=0;sdSkipped=0;sdTruncated=false;catalogIndex=0;
    if(!mountLibrarySD())return;
    DIR* dir=opendir("/sd/roms/scummvm");''')
a=s.index("static void homeUI(){")
b=s.index('extern "C" int prisma_scumm_run();',a)
assert "RetroUI::home" in s[a:b]
s=s[:a]+r'''// Only the chosen directory is enumerated; nothing is executed by this catalog.
static constexpr const char* dosRoots[]={"/sd/XT","/sd/386DX","/sd/486DX4"};
static constexpr const char* dosNames[]={"PRISMA XT","PRISMA 386DX","PRISMA 486DX4"};
static constexpr const char* dosLabels[]={"XT","386DX","486DX4"};
static constexpr unsigned dosLimit=64;
struct DosCatalogEntry {char name[128];uint8_t kind;};
static DosCatalogEntry dosEntries[dosLimit];
static int dosProfile=-1;
static unsigned dosCount=0,dosIndex=0,dosSkipped=0;
static bool dosTruncated=false,dosDirectoryFound=false;
static uint8_t dosFileKind(const char* name){
    const char* ext=strrchr(name,'.');
    if(!ext)return 0;
    if(!strcasecmp(ext,".zip"))return 2;
    if(!strcasecmp(ext,".7z"))return 3;
    if(!strcasecmp(ext,".img")||!strcasecmp(ext,".ima"))return 4;
    return 0;
}
static const char* dosKindLabel(uint8_t kind){
    switch(kind){case 1:return "CARPETA";case 2:return "ZIP";case 3:return "7Z";case 4:return "IMAGEN DE DISCO";default:return "?";}
}
static void scanDosLibrary(int profile){
    if(profile<0||profile>=3)return;
    dosProfile=profile;dosCount=0;dosIndex=0;dosSkipped=0;
    dosTruncated=false;dosDirectoryFound=false;
    if(!mountLibrarySD())return;
    DIR* dir=opendir(dosRoots[profile]);
    if(!dir)return;
    dosDirectoryFound=true;
    while(auto* e=readdir(dir)){
        const char* n=e->d_name;
        if(!n[0]||n[0]=='.')continue;
        if(strlen(n)>=sizeof(dosEntries[0].name)){dosSkipped++;continue;}
        char path[192];int len=snprintf(path,sizeof(path),"%s/%s",dosRoots[profile],n);
        if(len<0||len>=int(sizeof(path))){dosSkipped++;continue;}
        struct stat st;
        if(stat(path,&st)!=0){dosSkipped++;continue;}
        uint8_t kind=S_ISDIR(st.st_mode)?1:(S_ISREG(st.st_mode)?dosFileKind(n):0);
        if(!kind){dosSkipped++;continue;}
        if(dosCount==dosLimit){dosTruncated=true;break;}
        snprintf(dosEntries[dosCount].name,sizeof(dosEntries[0].name),"%s",n);
        dosEntries[dosCount++].kind=kind;
    }
    closedir(dir);
    for(unsigned i=1;i<dosCount;i++)for(unsigned j=i;j>0&&strcasecmp(dosEntries[j].name,dosEntries[j-1].name)<0;j--){
        DosCatalogEntry tmp=dosEntries[j];dosEntries[j]=dosEntries[j-1];dosEntries[j-1]=tmp;
    }
    Serial.printf("SC025 DOS CATALOG %s entries=%u skipped=%u truncated=%u\n",dosRoots[profile],dosCount,dosSkipped,dosTruncated);
}
static void homeUI(){
    selected=false;dosProfile=-1;
    auto& d=ui();const auto& t=RetroUI::themes[0];
    d.fillScreen(BG);
    RetroUI::center(d,240,20,"PRISMA RETRO",3,0xffff);
    RetroUI::center(d,240,52,"SC025 / BIBLIOTECAS SD",1,0x9cfa);
    for(int i=0;i<4;i++){
        int y=82+i*91;
        const char* title=i==0?"PRISMA SCUMMVM":dosNames[i-1];
        RetroUI::button(d,16,y,448,58,title,t,i==0);
        RetroUI::center(d,240,y+62,i==0?"FLASH + MICROSD / NATIVO":dosRoots[i-1]+3,1,0x9cfa);
    }
    showUI();
}
static void drawDosCarousel(){
    selected=true;
    auto& d=ui();const auto& t=RetroUI::themes[0];
    d.fillScreen(BG);
    RetroUI::button(d,12,10,90,44,"HOME",t);
    RetroUI::text(d,114,10,dosNames[dosProfile],2,0xffff);
    char line[64];snprintf(line,sizeof(line),"%s / %u ENTRADAS%s",dosRoots[dosProfile]+3,dosCount,dosTruncated?"+":"");
    RetroUI::text(d,114,39,line,1,0x9cfa);
    d.fillRoundRect(56,70,368,344,8,0x2124);
    d.drawRoundRect(56,70,368,344,8,0x5e9e);
    RetroUI::console(d,138,100,6,0);
    if(dosCount){
        const auto& item=dosEntries[dosIndex];
        // Bounded rows; FAT long names remain intact in the catalog.
        size_t len=strlen(item.name);
        for(unsigned row=0;row<5&&row*27<len;row++){
            char part[28];snprintf(part,sizeof(part),"%.27s",item.name+row*27);
            RetroUI::center(d,240,238+row*21,part,1,0xffff);
        }
        RetroUI::center(d,240,354,dosKindLabel(item.kind),2,0x9cfa);
        RetroUI::center(d,240,384,"MOTOR DOS PENDIENTE",1,0xfbe0);
    }else{
        RetroUI::center(d,240,280,!sdMounted?"SD NO DISPONIBLE":!dosDirectoryFound?"CARPETA NO EXISTE":"SIN JUEGOS",2,0xfbe0);
        RetroUI::center(d,240,320,dosRoots[dosProfile]+3,1,0x9cfa);
    }
    RetroUI::button(d,6,184,44,84,"<",t);
    RetroUI::button(d,430,184,44,84,">",t);
    RetroUI::button(d,318,436,150,32,"RELEER",t);
    snprintf(line,sizeof(line),"%u/%u",dosCount?dosIndex+1:0,dosCount);
    RetroUI::center(d,240,444,line,2,0x9cfa);
    snprintf(line,sizeof(line),"OMITIDOS: %u",dosSkipped);
    RetroUI::text(d,12,444,line,1,0x9cfa);
    showUI();
}
'''+s[b:]
# Explicitly intercept DOS library taps so the native SCUMM handoff is unreachable.
s=rep(s,'if(!selected&&hit(p,16,90,448,148)){scanSD();drawScummCarousel();}',r'''if(!selected&&hit(p,16,82,448,58)){dosProfile=-1;scanSD();drawScummCarousel();}
      else if(!selected&&hit(p,16,173,448,58)){scanDosLibrary(0);drawDosCarousel();}
      else if(!selected&&hit(p,16,264,448,58)){scanDosLibrary(1);drawDosCarousel();}
      else if(!selected&&hit(p,16,355,448,58)){scanDosLibrary(2);drawDosCarousel();}
      else if(selected&&dosProfile>=0){
          if(hit(p,12,10,90,44))homeUI();
          else if(dosCount&&hit(p,6,184,44,84)){dosIndex=(dosIndex+dosCount-1)%dosCount;drawDosCarousel();}
          else if(dosCount&&hit(p,430,184,44,84)){dosIndex=(dosIndex+1)%dosCount;drawDosCarousel();}
          else if(hit(p,318,436,150,32)){scanDosLibrary(dosProfile);drawDosCarousel();}
      }''')
p.write_text(s.replace("SC024","SC025"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC024","SC025"))
print("SC025: four independent catalogs, unchanged SCUMM runtime; DOS archive listing only")

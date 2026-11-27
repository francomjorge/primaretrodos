#!/usr/bin/env python3
"""SC026: three exclusive DOS ZIP catalogs, plus the existing native SCUMM catalog.
Catalog recognition is separate from executable compatibility.
"""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'static void scanSD(){','static void scanSD(bool scumm=true){')
s=rep(s,'    // Root path agreed for future platform catalogs; legacy remains readable.','    if(!scumm)return;\n    // Root path agreed for future platform catalogs; legacy remains readable.')
a=s.index('static void homeUI(){')
b=s.index('\n}',a)+2
assert 'RetroUI::home(ui(),counts);showUI();' in s[a:b]
s=s[:a]+r'''// DOS ZIPs are not loaded into the SCUMM engine. This release validates
// platform isolation, SD reads, and metadata cards before emulator integration.
struct DosCardMeta{
    const char* match;const char* title;const char* second;
    const char* yearMaker;const char* desc1;const char* desc2;
};
static const DosCardMeta dosMeta[]={
    {"streetrod2","STREET ROD 2","","1991 / CALIFORNIA DREAMS","Carreras y personalizacion","de autos clasicos."},
    {"princeofpersia","PRINCE OF PERSIA","","1989 / BRODERBUND","Plataformas y exploracion","en un palacio."},
    {"persia","PRINCE OF PERSIA","","1989 / BRODERBUND","Plataformas y exploracion","en un palacio."},
    {"simcity","SIMCITY","","1989 / MAXIS","Construccion y gestion","de ciudades."},
    {"civilization","CIVILIZATION","","1991 / MICROPROSE","Estrategia por turnos","a traves de la historia."},
    {"colonization","COLONIZATION","","1994 / MICROPROSE","Estrategia y gestion","de colonias."},
    {"wolfenstein3d","WOLFENSTEIN 3D","","1992 / ID SOFTWARE","Accion en primera persona","en laberintos."},
    {"3dduke","DUKE NUKEM 3D","","1996 / 3D REALMS","Accion en primera persona","con entornos interactivos."},
    {"dukenukem3d","DUKE NUKEM 3D","","1996 / 3D REALMS","Accion en primera persona","con entornos interactivos."},
    {"grandtheftauto","GRAND THEFT AUTO","","1997 / DMA DESIGN","Accion urbana","con perspectiva superior."},
    {"commandconquer","COMMAND & CONQUER","","1995 / WESTWOOD","Estrategia en tiempo real","y gestion de unidades."},
    {"ufo","UFO: ENEMY UNKNOWN","","1994 / MYTHOS / MICROPROSE","Estrategia tactica","contra una invasion alienigena."},
    {"carmensandiego","CARMEN SANDIEGO","","BRODERBUND","Investigacion y geografia","a traves de pistas."},
    {"incrediblemachine","THE INCREDIBLE","MACHINE","1993 / DYNAMIX","Rompecabezas de mecanica","y reacciones en cadena."},
    {"outrun","OUT RUN","","SEGA / VERSION POR VERIFICAR","Carreras de arcade","por rutas y paisajes."},
    {"indianajonesandthelastcrusade","INDIANA JONES","THE LAST CRUSADE","1989 / VERSION POR VERIFICAR","Aventura de Indiana Jones.","Edicion pendiente de reconocer."},
    {"indianajonesandthetempleofdoom","INDIANA JONES","TEMPLE OF DOOM","VERSION POR VERIFICAR","Accion y aventura.","Edicion pendiente de reconocer."},
    {"revengeoftheancients","INDIANA JONES","REVENGE OF THE ANCIENTS","VERSION POR VERIFICAR","Aventura de Indiana Jones.","Edicion pendiente de reconocer."}
};
struct DosZip{char file[256];uint64_t size;bool headerOK;};
static DosZip* dosZips=nullptr;
static constexpr unsigned dosMax=96;
static unsigned dosCount=0,dosIndex=0,dosOther=0;
static bool dosFolder=false,dosMore=false;
static int platformChoice=0;
static const char* const platformRoots[]={"/sd/SCUMMVM","/sd/XT","/sd/386DX","/sd/486DX4"};
static const char* const platformNames[]={"SCUMMVM","XT","386DX","486DX4"};
static const DosCardMeta* dosLookup(const char* name){
    char key[256];unsigned k=0;
    for(const unsigned char* p=(const unsigned char*)name;*p&&k<255;p++){
        unsigned c=*p;
        if(c>='A'&&c<='Z')c+=32;
        if((c>='a'&&c<='z')||(c>='0'&&c<='9'))key[k++]=char(c);
    }
    key[k]=0;
    for(const auto& m:dosMeta)if(strstr(key,m.match))return &m;
    return nullptr;
}
static void scanDosZips(){
    scanSD(false);
    dosCount=dosIndex=dosOther=0;dosFolder=dosMore=false;
    if(!sdMounted||platformChoice<1||platformChoice>3)return;
    if(!dosZips)dosZips=(DosZip*)heap_caps_calloc(dosMax,sizeof(DosZip),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!dosZips){Serial.println("DOS CATALOG MEMORY ERROR");return;}
    const char* root=platformRoots[platformChoice];
    DIR* d=opendir(root);if(!d){Serial.printf("DOS PATH MISSING %s\n",root);return;}
    dosFolder=true;
    while(auto* e=readdir(d)){
        const char* name=e->d_name;
        if(name[0]=='.'||strlen(name)>=sizeof(dosZips[0].file))continue;
        const char* ext=strrchr(name,'.');
        if(!ext||strcasecmp(ext,".zip")){dosOther++;continue;}
        char path[320];snprintf(path,sizeof(path),"%s/%s",root,name);
        struct stat st;if(stat(path,&st)||!S_ISREG(st.st_mode))continue;
        if(dosCount==dosMax){dosMore=true;break;}
        auto& z=dosZips[dosCount++];
        snprintf(z.file,sizeof(z.file),"%s",name);z.size=st.st_size;
        unsigned char sig[4]={};FILE* f=fopen(path,"rb");
        size_t n=f?fread(sig,1,4,f):0;if(f)fclose(f);
        z.headerOK=n==4&&sig[0]=='P'&&sig[1]=='K'&&sig[2]==3&&sig[3]==4;
        Serial.printf("DOS ZIP %s header=%s bytes=%llu\n",path,z.headerOK?"OK":"BAD",(unsigned long long)z.size);
        delay(1);
    }
    closedir(d);
    for(unsigned i=1;i<dosCount;i++)for(unsigned j=i;j&&strcasecmp(dosZips[j].file,dosZips[j-1].file)<0;j--){
        DosZip tmp=dosZips[j];dosZips[j]=dosZips[j-1];dosZips[j-1]=tmp;
    }
    Serial.printf("DOS CATALOG %s zip=%u other=%u\n",root,dosCount,dosOther);
}
static void homeUI(){
    selected=false;platformChoice=0;
    auto& d=ui();const auto& t=RetroUI::themes[0];d.fillScreen(BG);
    RetroUI::center(d,240,24,"PRISMA RETRO",3,0xffff);
    RetroUI::center(d,240,55,"SC026 / BIBLIOTECAS SD",1,0x9cfa);
    const char* subtitle[]={"MOTOR NATIVO / DEMO FLASH","8088 / 8086","80386DX","80486DX4"};
    for(int i=0;i<4;i++){
        int x=12+(i%2)*234,y=78+(i/2)*194;
        d.fillRoundRect(x,y,222,182,8,0x2124);
        d.drawRoundRect(x,y,222,182,8,0x5e9e);
        RetroUI::console(d,x+59,y+12,3,0);
        RetroUI::center(d,x+111,y+119,platformNames[i],2,0xffff);
        RetroUI::center(d,x+111,y+147,subtitle[i],1,0x9cfa);
    }
    showUI();
}
static void drawDosCarousel(){
    selected=true;auto& d=ui();const auto& t=RetroUI::themes[0];d.fillScreen(BG);
    RetroUI::button(d,12,10,90,44,"HOME",t);
    RetroUI::text(d,114,10,"PRISMA DOS",3,0xffff);
    char sub[64];snprintf(sub,sizeof(sub),"%s / %u ZIP%s",platformNames[platformChoice],dosCount,dosMore?"+":"");
    RetroUI::text(d,114,39,sub,1,0x9cfa);
    d.fillRoundRect(56,70,368,344,8,0x2124);d.drawRoundRect(56,70,368,344,8,0x5e9e);
    if(dosCount){
        const auto& z=dosZips[dosIndex];const auto* m=dosLookup(z.file);
        RetroUI::console(d,138,90,6,0);
        if(m){
            RetroUI::center(d,240,225,m->title,2,0xffff);
            RetroUI::center(d,240,251,m->second,2,0xffff);
            RetroUI::center(d,240,280,m->yearMaker,1,0x9cfa);
            RetroUI::center(d,240,307,m->desc1,1,0xffff);
            RetroUI::center(d,240,323,m->desc2,1,0xffff);
            RetroUI::center(d,240,345,"FICHA POR NOMBRE / NO VALIDADA",1,0x9cfa);
        }else{
            char line[31];snprintf(line,sizeof(line),"%.30s",z.file);
            RetroUI::center(d,240,225,line,2,0xffff);
            if(strlen(z.file)>30){snprintf(line,sizeof(line),"%.30s",z.file+30);RetroUI::center(d,240,251,line,2,0xffff);}
            RetroUI::center(d,240,300,"METADATOS PENDIENTES",1,0x9cfa);
        }
        snprintf(sub,sizeof(sub),"ZIP / %llu KB / %s",(unsigned long long)(z.size/1024),z.headerOK?"CABECERA OK":"ERROR");
        RetroUI::center(d,240,371,sub,1,z.headerOK?0x07e0:0xfbe0);
        RetroUI::center(d,240,392,"MOTOR DOS PENDIENTE",1,0xfbe0);
    }else{
        RetroUI::center(d,240,205,!sdMounted?"SD NO MONTADA":!dosFolder?"FALTA CARPETA":"SIN ARCHIVOS ZIP",2,0xfbe0);
        RetroUI::center(d,240,245,platformRoots[platformChoice]+3,2,0xffff);
        RetroUI::center(d,240,288,"COPIAR ZIP DIRECTAMENTE",1,0x9cfa);
    }
    RetroUI::button(d,6,184,44,84,"<",t);RetroUI::button(d,430,184,44,84,">",t);
    RetroUI::button(d,318,436,150,32,"RELEER",t,true);
    snprintf(sub,sizeof(sub),"%u/%u",dosCount?dosIndex+1:0,dosCount);
    RetroUI::center(d,240,444,sub,2,0x9cfa);
    showUI();
}'''+s[b:]
s=rep(s,'RetroUI::text(d,114,10,"PRISMA DOS",3,0xffff);\n    char summary[48];','RetroUI::text(d,114,10,"PRISMA SCUMM",3,0xffff);\n    char summary[48];')
a=s.index('if(!selected&&hit(p,16,90,448,148)){scanSD();drawScummCarousel();}')
b=s.index('\n    }',a)
assert 'menuCanvas.release();dos_start(lcd);' in s[a:b]
s=s[:a]+r'''if(!selected){
        for(int i=0;i<4;i++){
          int x=12+(i%2)*234,y=78+(i/2)*194;
          if(!hit(p,x,y,222,182))continue;
          platformChoice=i;
          if(!i){scanSD();drawScummCarousel();}
          else{scanDosZips();drawDosCarousel();}
          break;
        }
      }else if(hit(p,12,10,90,44))homeUI();
      else if(platformChoice){
        if(hit(p,6,184,44,84)&&dosCount){dosIndex=(dosIndex+dosCount-1)%dosCount;drawDosCarousel();}
        else if(hit(p,430,184,44,84)&&dosCount){dosIndex=(dosIndex+1)%dosCount;drawDosCarousel();}
        else if(hit(p,318,436,150,32)){scanDosZips();drawDosCarousel();}
      }else if(hit(p,6,184,44,84)){catalogIndex=(catalogIndex+sdCount)%(sdCount+1);drawScummCarousel();}
      else if(hit(p,430,184,44,84)){catalogIndex=(catalogIndex+1)%(sdCount+1);drawScummCarousel();}
      else if(hit(p,56,70,368,344)||hit(p,318,436,150,32)){
          if(dosZips){free(dosZips);dosZips=nullptr;}
          menuCanvas.release();dos_start(lcd);
      }'''+s[b:]
p.write_text(s.replace("SC025","SC026"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC025","SC026"))
print("SC026: independent root DOS ZIP catalogs and safe SCUMM launcher, filename metadata explicitly provisional")

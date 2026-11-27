#!/usr/bin/env python3
"""SC025: remove redundant EPX work for native filters; diagnose SD and support root catalog."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
# The native algorithms already reconstruct both subpixel rows. Do not run EPX
# on them as well, only to throw its output away. Preserve cursor and geometry.
s=rep(s,'                        const int q=edgeX[x],sx=q>>1;',r'''                        const int q=edgeX[x],sx=q>>1;
                        if(isNativeScaler()||visualMode==MMPX){
                            scaled[x]=isNativeScaler()?nativeScaleOut[half*2*w+q]:
                                mmpxRGB565(mmpxRows[half*2*w+q]);
                            if(sx>=lo&&sx<hi){
                                const uint8_t m=mouse[(sy-cy)*cw+sx-cx];
                                if(m!=key)scaled[x]=localCursorPal[m];
                            }
                            continue;
                        }''')
s=rep(s,'scaled[x]=isNativeScaler()?nativeScaleOut[half*2*w+q]:visualMode==MMPX?mmpxRGB565(mmpxRows[half*2*w+q]):localPal[v];','scaled[x]=localPal[v];')
# Retain per-mode timing for on-demand serial diagnostics, no log per frame.
s=rep(s,'static constexpr int visualCount=sizeof(visualNames)/sizeof(visualNames[0]);',r'''static constexpr int visualCount=sizeof(visualNames)/sizeof(visualNames[0]);
struct VideoStats {uint32_t calls,maxUs;uint64_t sumUs;};
static VideoStats videoStats[visualCount]={};
extern "C" void prisma_video_stats(){
    for(int i=0;i<visualCount;i++){
        auto& v=videoStats[i];if(!v.calls)continue;
        Serial.printf("VIDEO %s n=%lu avg_us=%lu max_us=%lu\n",visualNames[i],
            (unsigned long)v.calls,(unsigned long)(v.sumUs/v.calls),(unsigned long)v.maxUs);
    }
}
''')
s=rep(s,'renderCalls++;renderRows+=dirty;renderPixels+=written;renderWork+=micros()-begin;',r'''renderCalls++;renderRows+=dirty;renderPixels+=written;renderWork+=micros()-begin;
    if(written){
        uint32_t us=micros()-begin;auto& v=videoStats[int(visualMode)];
        v.calls++;v.sumUs+=us;if(us>v.maxUs)v.maxUs=us;
    }''')
s=rep(s,'extern "C" void prisma_diag_poll(){','extern "C" void prisma_video_stats();\nextern "C" void prisma_diag_poll(){')
s=rep(s,'            else if(!strcmp(line,":end"))scTestEnd();','            else if(!strcmp(line,":video"))prisma_video_stats();\n            else if(!strcmp(line,":end"))scTestEnd();')
# Catalog supports the newly agreed root path as well as the old layout.
# Store exact source path per entry; keep the existing folder-based save target
# for compatibility, and prefer root if both contain the same folder.
s=rep(s,'char folder[64],id[24];','char folder[64],id[24],path[160];')
s=rep(s,'static unsigned sdSkipped=0;','static unsigned sdSkipped=0,sdArchives=0,sdFolders=0,sdRoots=0;\nstatic uint32_t sdClock=0;')
a=s.index('static void scanSD(){');b=s.index('extern "C" bool prisma_game_from_sd()',a)
s=s[:a]+r'''static void scanSDRoot(const char* root){
    DIR* dir=opendir(root);
    if(!dir){Serial.printf("SD PATH MISSING %s\n",root);return;}
    sdRoots++;
    Serial.printf("SD PATH OK %s\n",root);
    while(auto* entry=readdir(dir)){
        const char* n=entry->d_name;
        if(n[0]=='.'||!n[0]||strlen(n)>=sizeof(sdGames[0].folder))continue;
        char path[160];snprintf(path,sizeof(path),"%s/%s",root,n);
        struct stat st;
        if(stat(path,&st)!=0){Serial.printf("SD STAT FAIL %s\n",path);continue;}
        if(!S_ISDIR(st.st_mode)){
            const char* ext=strrchr(n,'.');
            if(ext&&(!strcasecmp(ext,".zip")||!strcasecmp(ext,".7z")))sdArchives++;
            continue;
        }
        sdFolders++;
        bool duplicate=false;
        for(unsigned i=0;i<sdCount;i++)if(!strcasecmp(sdGames[i].folder,n)){duplicate=true;break;}
        if(duplicate){sdSkipped++;continue;}
        if(sdCount==maxSDGames){sdTruncated=true;break;}
        char id[24]={};
        if(!prisma_detect_sd(path,id,sizeof(id))||!findGameMeta(id)){
            sdSkipped++;Serial.printf("SD GAME SKIP %s\n",path);continue;
        }
        auto& g=sdGames[sdCount++];
        snprintf(g.folder,sizeof(g.folder),"%s",n);
        snprintf(g.id,sizeof(g.id),"%s",id);
        snprintf(g.path,sizeof(g.path),"%s",path);
        Serial.printf("SD GAME OK %s id=%s\n",path,id);
        delay(1);
    }
    closedir(dir);
}
static void scanSD(){
    sdCount=sdSkipped=sdArchives=sdFolders=sdRoots=0;sdTruncated=false;catalogIndex=0;
    pinMode(39,OUTPUT);digitalWrite(39,HIGH);
    pinMode(42,OUTPUT);digitalWrite(42,HIGH);
    // Rescan only from the menu, before any game opens SD files.
    if(sdMounted){SD.end();sdMounted=false;}
    SPI.begin(48,41,47,42);
    const uint32_t clocks[]={4000000,400000};
    for(uint32_t hz:clocks){
        Serial.printf("SD MOUNT TRY SPI CS42 CLK48 MOSI47 MISO41 hz=%lu\n",(unsigned long)hz);
        if(SD.begin(42,SPI,hz,"/sd",10,false)){
            sdMounted=true;sdClock=hz;break;
        }
        SD.end();digitalWrite(42,HIGH);delay(20);
    }
    if(!sdMounted){sdClock=0;Serial.println("SD MOUNT FAILED (NO FORMAT)");return;}
    Serial.printf("SD MOUNT OK type=%u size_MB=%llu hz=%lu\n",
        (unsigned)SD.cardType(),(unsigned long long)(SD.cardSize()/1048576ULL),(unsigned long)sdClock);
    // Root path agreed for future platform catalogs; legacy remains readable.
    scanSDRoot("/sd/SCUMMVM");
    scanSDRoot("/sd/roms/scummvm");
    for(unsigned i=1;i<sdCount;i++){
        for(unsigned j=i;j>0&&strcasecmp(findGameMeta(sdGames[j].id)->title1,findGameMeta(sdGames[j-1].id)->title1)<0;j--){
            GameInfo tmp=sdGames[j];sdGames[j]=sdGames[j-1];sdGames[j-1]=tmp;
        }
    }
    Serial.printf("SD CATALOG roots=%u folders=%u games=%u skipped=%u archives=%u\n",
        sdRoots,sdFolders,sdCount,sdSkipped,sdArchives);
}
'''+s[b:]
s=rep(s,'snprintf(path,256,"/sd/roms/scummvm/%s",name);','snprintf(path,256,"%s",sdGames[catalogIndex-1].path);')
s=rep(s,'    if(!sdMounted)RetroUI::center(d,240,421,"SD NO DISPONIBLE",1,0xfbe0);',r'''    if(!sdMounted)RetroUI::center(d,240,421,"SD: ERROR DE MONTAJE",1,0xfbe0);
    else if(!sdRoots)RetroUI::center(d,240,421,"SD OK / FALTA SCUMMVM",1,0xfbe0);
    else if(!sdCount&&sdArchives)RetroUI::center(d,240,421,"SD OK / DESCOMPRIMIR ZIP",1,0xfbe0);''')
p.write_text(s.replace("SC024","SC025"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC024","SC025"))
print("SC025: skip unused EPX for native scalers, :video timing, dual SD paths, 4MHz/400kHz retry and catalog diagnostics; no formatting")

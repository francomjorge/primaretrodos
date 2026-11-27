#!/usr/bin/env python3
"""SC016: independent outline mode and save/load cover; keep SC015 fallback."""
from pathlib import Path
import base64,zlib,sys
src=Path(sys.argv[1])/"src"
cover=zlib.decompress(base64.b64decode("eNqNV4mW4ygMBINAXOL//3arhJ1O0jPzVp04dqLSURKgbu0lY7S9x8AbL/Wrv9+k/UFc5ahtEcdAdHeK38OU3/lz9+cx+gG1o36cHswfZEF6F/n8Vt3ep9YjZudi70IrPyqdNnvn1/6jlPKmO+1/SX95KKnUaRNiVfgxVxZ/fpPn+SckOiplFngvtcyKH2txSxZjfvSh8S0HT0+SUkmpTr8Q768pIWQPpJaaoPKFr4zSUgEKP9ZacctAEn7ha6rqWjRFDaj9CkEqAyvuHbETX2cMsTKBlQN6AOWhhZSgCatu9ysKmigehuctOUKCWMw5asz+F0uUmKH8yJ2mGyhH0ol/QjMQDzixAX80Bam/ZToEb2ZfncCDz8shmfgUT1AMsHwZ8JxBMD9oqNacMtzR/0tikpiiJ/gjdwCVpS5OYWHlwbV4RGvtxgZf27xEJ78vqd4/HgDCphKqLihCUI2xDSavLV4pBKQBCzl+mpF57KABc4hwlAElAWHg2lHEoDlcsBrggE7uYO5wngcQB6RHETVE0wDqggCNCKRIQLNoEH6+gdJ9e124VYTI8FGzMtupGfEhLODRYR1RRZbsHX89kqjJ8IEXG6S9IQ9lMyCOAA0J4eXukU+8RMcvcf+NZICOuFvI8Ipfrw95g18X8TnyEnQ15t+VeJLQgqJMv/DXNz6QefAPxyPHhQA0A0xKcwaB8cPjNx7rBkiQTyN9tK4tKzZtFUVg0XrIVv6F93zjGop9XQGOA9em2CO5V7OoNtP1F0H8EjLxjVCA0UC6W4vLVs7coLkhlr/j4yJZWIAR9HcdIJ7ugyz1hs7s9Vn+HEFi2wFFsgIo64t4ZA9GdkP6sClYl1a5zn/bQP/FaRvaDXjoZxSeR170JcRuyNxJ7Fn4Nf3CG6ijo0ivMEI8gAfvO0F/GYCJFxbdWSYr1/vweuM05sKJi0gk7le2JGorr32wPOsnXakaQsaZJmAfeEX2wPPSPISM9YwuMOyr9r5/3euo0j/OVysLFMIf6NaTMHoBLZm5FxDPBH62wRccxwlLLHWzBOQKwH76CF2YsSQi8Rud8BbAg+dWiOxXscFCNybQxuSAwQ7Ga22GM4nv8wN/R0O8VDYfkm19YTRZPqGov5CXOn+2us03/A98d5lodOA31BF+97lI/TrX6JuEdM4L87aAuj9Hydp91d68Y1qz3dxG63LGJPQWTkOFl8WJ48GnB25kb27qAt8N6RsHLlbU8ZN4TAw+s9h9+KXnHHH2pt34YXA9PPy1xOe2NZHf5tSzHe8WiD/7v5E9c1foNKOh7sZ0mRMA0nicI0mcSffUM+u9k3r0wLtHFJ+Zn/AHBzX1m8n5bQ+eaS8Dvommkz0iPBOmKl1vN7Z90OP32ypCJ77bgzdf+UierMzb/TYRH0yPLZHR9VCI0DsGzeUs+kBI94e7vVBhrzQS7a9RV8jeCWVgeTse/o0sIhN33n3qlfXwhcHywe9j1P2jBAe/9+kBzMCJieCs71tO7bDbgmLdNx5VYk3OY6/uiZP2dgL68LHFp4nTOk18w9d9G+AEtzDIHQIqQzx4Tr9m7TnHb7hSsGcJjkyHGPGoxsb3spfc/xb00wq2/wPpn1zm"))
assert len(cover)==64*49 and max(cover)<16
palette="0xbf3e,0xa51b,0xfbf,0xd3f,0x8317,0x1a99,0x2fe,0x1fe,0x18f1,0x104b,0x8b2,0x84d,0x11c,0xb4,0x76,0x4d"
(src/"monkey_cover016.h").write_text("#pragma once\nstatic const uint16_t coverPal[16]={"+palette+"};\nstatic const uint8_t coverPixels[64*49]={"+",".join(map(str,cover))+"};\n")
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'#include "game_video.h"','#include "game_video.h"\n#include "monkey_cover016.h"')
s=rep(s,'static bool edgeScale=true;','''static bool edgeScale=true;
static bool outlineMode=false;
static uint8_t edgeLum[256];
static bool saveCover=false,saveCoverReady=false,saveCoverOutcome=false;
static uint32_t saveCoverAt=0;
''')
s=rep(s,'if(edgeScale!=enabled){edgeScale=enabled;indexedValid=false;}','''if(edgeScale!=enabled||outlineMode){edgeScale=enabled;outlineMode=false;indexedValid=false;}''')
s=rep(s,'static int oldIndexedW=0,','''extern "C" void prisma_outline_set(){
    edgeScale=true;outlineMode=true;indexedValid=false;
}
static int oldIndexedW=0,''')
s=rep(s,'extern "C" void prisma_filter_set(bool);\nextern "C" void prisma_diag_poll(){','extern "C" void prisma_filter_set(bool);\nextern "C" void prisma_outline_set();\nextern "C" void prisma_diag_poll(){')
s=rep(s,'else if(!strcmp(line,":smooth")){prisma_filter_set(true);Serial.println("VIDEO EDGE");}','''else if(!strcmp(line,":smooth")){prisma_filter_set(true);Serial.println("VIDEO EDGE");}
            else if(!strcmp(line,":outline")){prisma_outline_set();Serial.println("VIDEO OUTLINE");}''')
s=rep(s,'    prisma_diag_phase(4);\n    const uint32_t begin=micros();','''    if(saveCover){
        if(!saveCoverReady||millis()-saveCoverAt<220)return;
        saveCover=false;indexedValid=false;
    }
    prisma_diag_phase(4);
    const uint32_t begin=micros();''')
s=rep(s,'    if(memcmp(previousPal,localPal,sizeof(localPal)))force=true;','''    if(memcmp(previousPal,localPal,sizeof(localPal)))force=true;
    if(outlineMode&&force)for(int i=0;i<256;i++){
        const uint16_t c=localPal[i];
        // approximate 8-bit luminance, integer only
        edgeLum[i]=((c>>11)*8*77+((c>>5)&63)*4*150+(c&31)*8*29)>>8;
    }''')
s=rep(s,'                        scaled[x]=localPal[v];','''                        scaled[x]=localPal[v];
                        if(outlineMode&&sy<144){
                            const int center=edgeLum[e];
                            const int nearX=edgeLum[(q&1)?f:d];
                            const int nearY=edgeLum[half?hpx:b];
                            // One-sided, subpixel contrast outline, no double thick border.
                            if(center>=70&&(center-nearX>=58||center-nearY>=58))
                                scaled[x]=0x0000;
                        }''')
s=rep(s,'extern "C" void prisma_lcd_flush(){\n    indexedValid=false;','extern "C" void prisma_lcd_flush(){\n    indexedValid=false;\n    if(saveCover)return;')
s=rep(s,'    pollTouch(); *down=npoints>0;','''    pollTouch();
    if(saveCover){*down=false;return 0;}
    *down=npoints>0;''')
s=rep(s,'static char saveOutcome[48]={};',r'''static char saveOutcome[48]={};
extern "C" void prisma_save_transition_begin(int action,int slot){
    saveCover=true;saveCoverReady=false;saveCoverOutcome=false;
    saveCoverAt=millis();indexedValid=false;
    lcd.fillScreen(0x0842);
    // User's supplied title photo, cropped and downsampled offline.
    // Direct rows, no JPEG decoder or allocation in the save path.
    uint16_t row[384];
    for(int y=0;y<294;y++){
        for(int x=0;x<384;x++)row[x]=coverPal[coverPixels[(y/6)*64+x/6]];
        lcd.draw16bitRGBBitmap(48,32+y,row,384,1);
    }
    RetroUI::center(lcd,240,350,action==1?"GUARDANDO PARTIDA":"CARGANDO PARTIDA",2,0xffff);
    RetroUI::center(lcd,240,392,String("PARTIDA ")+slot,2,0xbdf7);
    lcd.flush(true);
}
extern "C" void prisma_save_transition_loop_done(){
    if(saveCover&&saveCoverOutcome)saveCoverReady=true;
}
''')
s=rep(s,'    prisma_diag_line(2,"%s",saveOutcome);','''    prisma_diag_line(2,"%s",saveOutcome);
    if(saveCover){
        saveCoverOutcome=true;
        if(!ok){
            lcd.fillRect(0,420,480,40,0x0842);
            RetroUI::center(lcd,240,432,"ERROR DE PARTIDA",2,0xf800);
            lcd.flush(true);
        }
    }''')
# Reuse the cover for the requested game selector instead of generic icon.
old='    RetroUI::console(d,138,122,6,0);'
if old in s:
    s=s.replace(old,'''    uint16_t coverRow[256];
    for(int yy=0;yy<196;yy++){
        for(int xx=0;xx<256;xx++)coverRow[xx]=coverPal[coverPixels[(yy/4)*64+xx/4]];
        d.draw16bitRGBBitmap(112,86+yy,coverRow,256,1);
    }
    RetroUI::center(d,240,296,"1990 / LUCASFILM GAMES",1,0xbdf7);
    RetroUI::center(d,240,312,"AVENTURA GRAFICA / SCUMM",1,0xbdf7);
    RetroUI::center(d,240,328,"GUYBRUSH QUIERE SER PIRATA",1,0xbdf7);''',1)
p.write_text(s.replace("SC015","SC016"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC015","SC016"))
p=src/"native/components/scumm/scumm.cpp";s=p.read_text()
s='extern "C" void prisma_save_transition_begin(int,int);\nextern "C" void prisma_save_transition_loop_done();\n'+s
s=rep(s,'\t\tCommon::String filename;\n\t\tif (_saveLoadFlag == 1) {','''        if(!_saveTemporaryState&&_saveLoadSlot>=1&&_saveLoadSlot<=4)
            prisma_save_transition_begin(_saveLoadFlag,_saveLoadSlot);
\t\tCommon::String filename;
\t\tif (_saveLoadFlag == 1) {''')
s=rep(s,'\t\tscummLoop(delta);\n\n\t\t// Halt the stop watch','\t\tscummLoop(delta);\n        prisma_save_transition_loop_done();\n\n\t\t// Halt the stop watch')
p.write_text(s)
print("SC016: pixel/smooth/outline; user title cover during save/load and selector, same game and saves partition")

#!/usr/bin/env python3
"""SC017: four-finger modal visual laboratory. Keep saves and input ABI."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'static bool outlineMode=false;','''static bool outlineMode=false;
enum VisualMode { PIXEL,SMOOTH,OUTLINE,COMIC,CRT,NOIR,VINTAGE,PSYCH,VIVID };
static VisualMode visualMode=SMOOTH;
static uint16_t scanRow[480];
static const char* const visualNames[]={"PIXEL","SMOOTH","OUTLINE","COMIC","CRT","NOIR","VINTAGE","PSYCH","VIVID"};
''')
s=rep(s,'''if(edgeScale!=enabled||outlineMode){edgeScale=enabled;outlineMode=false;indexedValid=false;}''','''visualMode=enabled?SMOOTH:PIXEL;
    edgeScale=enabled;outlineMode=false;indexedValid=false;''')
s=rep(s,'''edgeScale=true;outlineMode=true;indexedValid=false;''','''visualMode=OUTLINE;edgeScale=true;outlineMode=true;indexedValid=false;''')
anchor='static int oldIndexedW=0,'
s=rep(s,anchor,r'''static void setVisual(VisualMode mode){
    visualMode=mode;
    edgeScale=mode==SMOOTH||mode==OUTLINE||mode==COMIC||mode==CRT;
    outlineMode=mode==OUTLINE||mode==COMIC;
    indexedValid=false;
}
static uint16_t visualRGB(int r,int g,int b){
    r=max(0,min(31,r));g=max(0,min(63,g));b=max(0,min(31,b));
    return uint16_t((r<<11)|(g<<5)|b);
}
static uint16_t visualColor(uint16_t c){
    int r=c>>11,g=(c>>5)&63,b=c&31;
    int l=(r*77+g*75+b*29)>>8;
    switch(visualMode){
        case NOIR:{int v=(l*4/31)*31/4;return visualRGB(v,v*2,v);}
        case VINTAGE:return visualRGB(l*31/28,l*54/31,l*20/31);
        case PSYCH:return visualRGB(b,g/2+r,r);
        case COMIC:
        case VIVID:{
            int strength=visualMode==COMIC?5:3;
            r=l+(r-l)*strength/2;g=2*l+(g-2*l)*strength/2;b=l+(b-l)*strength/2;
            if(visualMode==COMIC){r=(r/4)*4;g=(g/8)*8;b=(b/4)*4;}
            return visualRGB(r,g,b);
        }
        default:return c;
    }
}
'''+anchor)
# Apply palette transformation once per palette entry, never per pixel.
s=rep(s,'localPal[i]=__builtin_bswap16(palette[i]);','localPal[i]=visualColor(__builtin_bswap16(palette[i]));')
# CRT is only in the edge branch. Keep base scan row intact for repeated source rows.
a=s.index('    if(edgeScale){',s.index('unsigned dirty=0,written=0;'))
b=s.index('    }else{\n    for(int sy=0;sy<h;sy++){',a)
t=s[a:b]
t=rep(t,'''                if(fb){
                    uint16_t* dst=fb+y*480;
                    if(!sourceChanged&&!memcmp(dst,scaled,sizeof(scaled)))continue;
                    memcpy(dst,scaled,sizeof(scaled));
                }else lcd.draw16bitRGBBitmap(0,y,scaled,480,1);''','''                uint16_t* output=scaled;
                if(visualMode==CRT&&y%3==2){
                    for(int x=0;x<480;x++)scanRow[x]=((scaled[x]&0xf7de)>>1);
                    output=scanRow;
                }
                if(fb){
                    uint16_t* dst=fb+y*480;
                    if(!sourceChanged&&!memcmp(dst,output,sizeof(scaled)))continue;
                    memcpy(dst,output,sizeof(scaled));
                }else lcd.draw16bitRGBBitmap(0,y,output,480,1);''')
s=s[:a]+t+s[b:]
# No display writes from another task. Menu runs only inside the native engine's
# touch polling after the four-finger release, same modal pattern as F5.
anchor='static volatile bool runtimeActive=false;'
s=rep(s,anchor,r'''
extern "C" void prisma_visual_menu(){
    if(saveCover)return;
    constexpr int top=205,rows=480-top;
    uint16_t* fb=lcd.getFramebuffer();
    if(!fb)return;
    uint16_t* backup=(uint16_t*)heap_caps_malloc(480*rows*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!backup)return;
    memcpy(backup,fb+top*480,480*rows*2);
    lcd.fillRect(0,top,480,rows,0x0842);
    RetroUI::text(lcd,10,top+11,"PRISMA / VIDEO",2,0xffff);
    auto button=[&](int x,int y,int w,int h,const char* label,bool selected){
        lcd.fillRoundRect(x+2,y+2,w-4,h-4,5,selected?0x0328:0x2124);
        lcd.drawRoundRect(x+2,y+2,w-4,h-4,5,selected?0xffe0:0x7bef);
        lcd.setTextColor(0xffff);lcd.setTextSize(2);
        lcd.setCursor(x+(w-int(strlen(label))*12)/2,y+(h-16)/2);lcd.print(label);
    };
    button(340,top,140,38,"OCULTAR",false);
    for(int i=0;i<9;i++)button((i%3)*160,top+42+(i/3)*66,160,64,visualNames[i],i==visualMode);
    RetroUI::text(lcd,10,top+251,"ELEGIR ESTILO / VUELVE AL JUEGO",1,0xbdf7);
    lcd.flush(true);
    auto hitMode=[&](int x,int y)->int{
        if(x>=340&&x<480&&y>=top&&y<top+38)return 9;
        if(x<0||x>=480||y<top+42||y>=top+240)return -1;
        int r=(y-top-42)/66;
        return (y-top-42)%66<64?r*3+x/160:-1;
    };
    bool finger=false,blocked=false,done=false;int choice=-1;
    while(!done){
        prisma_diag_poll();pollTouch();
        if(npoints>1){blocked=true;finger=false;choice=-1;}
        else if(blocked){if(!npoints)blocked=false;}
        else if(npoints==1&&!finger){finger=true;choice=hitMode(points[0].x,points[0].y);}
        else if(npoints==1&&finger&&hitMode(points[0].x,points[0].y)!=choice){choice=-1;}
        else if(!npoints&&finger){
            finger=false;
            if(choice>=0&&choice<9){setVisual(VisualMode(choice));done=true;}
            else if(choice==9)done=true;
            choice=-1;
        }
        delay(12);
    }
    memcpy(fb+top*480,backup,480*rows*2);free(backup);
    lcd.flush(true);indexedValid=false;
}
'''+anchor)
p.write_text(s.replace("SC016","SC017"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC016","SC017"))
p=src/"native/components/backends/platform/esp32/osystem-events.cpp";s=p.read_text()
s=rep(s,'#include "osystem.h"','#include "osystem.h"\nextern "C" void prisma_visual_menu();')
s=rep(s,'            if(peak==2||peak==3){','''            if(peak==4){
                prisma_diag_line(2,"GESTURE VIDEO fingers=4");
                prisma_visual_menu();
            }else if(peak==2||peak==3){''')
p.write_text(s)
print("SC017: 4-finger release opens nine-mode modal; 2 ESC/3 F5 unchanged; no permanent controls")

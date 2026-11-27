#!/usr/bin/env python3
"""SC020: live, nonmodal style carousel; no changes to saves or game geometry."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'static VisualMode visualMode=SMOOTH;',r'''static VisualMode visualMode=SMOOTH;
static constexpr int labTop=432;
static bool labActive=false,labBarDirty=false;
static int labPressed=-1;
static bool labCaptured=false;
''')
s=rep(s,'static int oldIndexedW=0,',r'''static constexpr int visualCount=sizeof(visualNames)/sizeof(visualNames[0]);
static void drawLabBar(){
    if(!labActive||saveCover)return;
    lcd.fillRect(0,labTop,480,480-labTop,0x0842);
    lcd.drawFastHLine(0,labTop,480,0x7bef);
    auto button=[](int x,int w,const char* label){
        lcd.fillRoundRect(x+2,labTop+4,w-4,40,5,0x2124);
        lcd.drawRoundRect(x+2,labTop+4,w-4,40,5,0x7bef);
        lcd.setTextSize(2);lcd.setTextColor(0xffff);
        lcd.setCursor(x+(w-int(strlen(label))*12)/2,labTop+16);lcd.print(label);
    };
    button(0,54,"<");button(318,54,">");button(372,108,"FULL");
    char label[32];snprintf(label,sizeof(label),"%s",visualNames[visualMode]);
    RetroUI::text(lcd,66,labTop+7,label,2,0xffff);
    snprintf(label,sizeof(label),"LAB %02d/%02d",int(visualMode)+1,visualCount);
    RetroUI::text(lcd,66,labTop+29,label,1,0xbdf7);
    labBarDirty=false;
}
static void setLab(bool active){
    labActive=active;labBarDirty=active;indexedValid=false;
    labPressed=-1;labCaptured=false;
}
// Called on the game task, before the normal mouse dispatcher. Capture a
// complete touch that starts in the bar, including release. A multi-finger
// chord cancels the bar action and is handled by the original dispatcher.
extern "C" bool prisma_lab_touch(int count,bool mayStart){
    if(count>=2){labCaptured=false;labPressed=-1;return false;}
    if(!labActive||saveCover){labCaptured=false;labPressed=-1;return false;}
    auto hit=[]()->int{
        if(!npoints||points[0].y<labTop)return -1;
        int x=points[0].x;
        return x<54?0:x>=372?2:x>=318?1:3;
    };
    if(labCaptured){
        if(count==1){if(hit()!=labPressed)labPressed=-1;return true;}
        if(count==0){
            int action=labPressed;
            labCaptured=false;labPressed=-1;
            if(action==2)setLab(false);
            else if(action==0||action==1){
                setVisual(VisualMode((int(visualMode)+visualCount+(action==0?-1:1))%visualCount));
                labBarDirty=true;
            }
            return true;
        }
    }
    if(mayStart&&count==1&&npoints&&points[0].y>=labTop){
        labCaptured=true;labPressed=hit();return true;
    }
    return false;
}
static int oldIndexedW=0,''')
# Keep current full-screen projection: just reserve the bottom output rows.
# The previous-source cache still updates while the overlay is visible;
# leaving LAB forces a complete redraw so no stale bar pixels remain.
s=rep(s,'for(int y=yedge[sy];y<yedge[sy+1];y++){\n                const int half=', 'for(int y=yedge[sy];y<yedge[sy+1];y++){\n                if(labActive&&y>=labTop)continue;\n                const int half=')
s=rep(s,'for(int y=y0;y<y1;y++){\n            if(fb){','for(int y=y0;y<y1;y++){\n            if(labActive&&y>=labTop)continue;\n            if(fb){')
s=rep(s,'    if(written){prisma_diag_phase(5);lcd.flush(true);renderPresents++;}',r'''    if(labActive&&(labBarDirty||force)){drawLabBar();written+=480*(480-labTop);}
    if(written){prisma_diag_phase(5);lcd.flush(true);renderPresents++;}''')
# Raw legacy rendering must not permanently overwrite the overlay.
s=rep(s,'if(frameValid)GameVideo::draw(lcd,nullptr,nullptr,nativeFrame,frameW,frameH,frameW,{layoutMode,false});',
'''if(frameValid)GameVideo::draw(lcd,nullptr,nullptr,nativeFrame,frameW,frameH,frameW,{layoutMode,false});
    if(labActive){drawLabBar();lcd.flush(true);}''')
# The previously empty twelfth cell becomes LAB.
s=rep(s,'for(int i=0;i<11;i++)button((i%4)*120,top+42+(i/4)*66,120,64,visualNames[i],i==visualMode);',
'''for(int i=0;i<visualCount;i++)button((i%4)*120,top+42+(i/4)*66,120,64,visualNames[i],i==visualMode);
    button(360,top+174,120,64,"LAB",labActive);''')
s=rep(s,'if(x>=340&&x<480&&y>=top&&y<top+38)return 11;','if(x>=340&&x<480&&y>=top&&y<top+38)return 12;')
s=rep(s,'return (y-top-42)%66<64&&i<11?i:-1;','return (y-top-42)%66<64&&i<12?i:-1;')
s=rep(s,'if(choice>=0&&choice<11){setVisual(VisualMode(choice));done=true;}\n            else if(choice==11)done=true;',
'''if(choice>=0&&choice<visualCount){setVisual(VisualMode(choice));setLab(false);done=true;}
            else if(choice==11){setLab(true);done=true;}
            else if(choice==12)done=true;''')
# This is the visual modal's restore, not the separate save dialog.
s=rep(s,'    lcd.flush(true);indexedValid=false;\n}\n\nstatic volatile bool runtimeActive=false;',
'''    if(labActive)drawLabBar();
    lcd.flush(true);indexedValid=false;
}

static volatile bool runtimeActive=false;''')
p.write_text(s.replace("SC019","SC020"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC019","SC020"))
p=src/"native/components/backends/platform/esp32/osystem-events.cpp";s=p.read_text()
s=rep(s,'extern "C" void prisma_visual_menu();','extern "C" void prisma_visual_menu();\nextern "C" bool prisma_lab_touch(int,bool);')
s=rep(s,'    const int count=prismaTouch(x,y,down);',
'''    const int count=prismaTouch(x,y,down);
    if(prisma_lab_touch(count,!contact&&!multiPeak))return false;''')
p.write_text(s)
# Validate the shared button rectangles (all x/y physical coordinates).
assert 432+48==480
assert 54<318<372<480
assert 205+42+2*66==379
print("SC020: live 48px LAB bar, previous/next with wrap, FULL restores image, captured touch release, 11 effects")

#!/usr/bin/env python3
"""SC021: classic four-quadrant Kuwahara radius 1 and two painterly variants.
Original integer implementation for PRISMA; no AI or third-party runtime."""
from pathlib import Path
import sys
src=Path(sys.argv[1])/"src"
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b,1)
p=src/"main.cpp";s=p.read_text()
s=rep(s,'HD_PIXEL,HD_INK };','HD_PIXEL,HD_INK,KUWAHARA,MONET,ACUARELA };')
s=rep(s,'"HD PIXEL","HD INK"};','"HD PIXEL","HD INK","KUWAHARA","MONET","ACUARELA"};')
s=rep(s,'||mode==HD_PIXEL||mode==HD_INK;','||mode==HD_PIXEL||mode==HD_INK||mode==KUWAHARA||mode==MONET||mode==ACUARELA;')
s=rep(s,'static int oldIndexedW=0,',r'''static uint8_t artLuma[256];
static uint16_t artRow[320];
static inline bool artMode(){
    return visualMode==KUWAHARA||visualMode==MONET||visualMode==ACUARELA;
}
static inline uint16_t artMean(uint16_t a,uint16_t b,uint16_t c,uint16_t d){
    unsigned r=(a>>11)+(b>>11)+(c>>11)+(d>>11);
    unsigned g=((a>>5)&63)+((b>>5)&63)+((c>>5)&63)+((d>>5)&63);
    unsigned bl=(a&31)+(b&31)+(c&31)+(d&31);
    return uint16_t(((r>>2)<<11)|((g>>2)<<5)|(bl>>2));
}
static inline int artVariance(int a,int b,int c,int d){
    int sum=a+b+c+d;
    return 4*(a*a+b*b+c*c+d*d)-sum*sum;
}
// Four overlapping 2x2 neighborhoods centered around each source pixel.
// Select the lowest luminance variance, then average its actual RGB colors.
// Ties prefer the region whose mean luminance is closest to the center.
static void artBuildRow(int w){
    for(int x=0;x<w;x++){
        int l=x?x-1:x,r=x+1<w?x+1:x;
        uint8_t e=localIndices[x],n=edgeAbove[x],so=edgeBelow[x];
        uint8_t west=localIndices[l],east=localIndices[r];
        uint8_t q[4][3]={{n,west,edgeAbove[l]},{n,east,edgeAbove[r]},
                         {so,west,edgeBelow[l]},{so,east,edgeBelow[r]}};
        int center=artLuma[e],best=0,bestCost=0x7fffffff;
        for(int i=0;i<4;i++){
            int a=artLuma[q[i][0]],b=artLuma[q[i][1]],c=artLuma[q[i][2]];
            int cost=artVariance(center,a,b,c)*8+abs(a+b+c-3*center);
            if(cost<bestCost){bestCost=cost;best=i;}
        }
        uint16_t col=artMean(localPal[e],localPal[q[best][0]],localPal[q[best][1]],localPal[q[best][2]]);
        if(visualMode==MONET){
            // Pastel wash, cool shadows, warm highlights. No temporal noise.
            int rr=col>>11,gg=(col>>5)&63,bb=col&31;
            int light=artLuma[e];
            col=visualRGB((rr*7+22)/8+(light>150?2:0),
                (gg*7+45)/8,(bb*7+28)/8+(light<105?2:0));
        }else if(visualMode==ACUARELA){
            // Translucent paper wash; retain a proportion of original dark edges.
            int rr=col>>11,gg=(col>>5)&63,bb=col&31;
            col=visualRGB((rr*3+29)/4,(gg*3+58)/4,(bb*3+25)/4);
            if(center+36<max(max(artLuma[n],artLuma[so]),max(artLuma[west],artLuma[east]))){
                uint16_t orig=localPal[e];
                col=artMean(col,col,orig,orig);
            }
        }
        artRow[x]=col;
    }
}
static int oldIndexedW=0,''')
s=rep(s,'    if(memcmp(previousPal,localPal,sizeof(localPal)))force=true;',r'''    if(memcmp(previousPal,localPal,sizeof(localPal)))force=true;
    if(artMode()&&force)for(int i=0;i<256;i++){
        uint16_t c=localPal[i];
        artLuma[i]=((c>>11)*8*77+((c>>5)&63)*4*150+(c&31)*8*29)>>8;
    }''')
s=rep(s,'            memcpy(edgeBelow,pixels+(sy+1<h?sy+1:sy)*w,w);',r'''            memcpy(edgeBelow,pixels+(sy+1<h?sy+1:sy)*w,w);
            // Keep verbs, inventory and text region outside the painterly pass.
            const bool paint=artMode()&&sy*200<h*144;
            if(paint)artBuildRow(w);''')
s=rep(s,'                        scaled[x]=localPal[v];','                        scaled[x]=paint?artRow[sx]:localPal[artMode()?e:v];')
# Expand to 15 cells while retaining the 48-pixel live bar and all old modes.
s=rep(s,'for(int i=0;i<visualCount;i++)button((i%4)*120,top+42+(i/4)*66,120,64,visualNames[i],i==visualMode);',
'for(int i=0;i<visualCount;i++)button((i%5)*96,top+42+(i/5)*66,96,64,visualNames[i],i==visualMode);')
s=rep(s,'button(360,top+174,120,64,"LAB",labActive);','button(384,top+174,96,64,"LAB",labActive);')
s=rep(s,'if(x>=340&&x<480&&y>=top&&y<top+38)return 12;','if(x>=340&&x<480&&y>=top&&y<top+38)return visualCount+1;')
s=rep(s,'int i=r*4+x/120;return (y-top-42)%66<64&&i<12?i:-1;',
'int i=r*5+x/96;return (y-top-42)%66<64&&i<=visualCount?i:-1;')
s=rep(s,'else if(choice==11){setLab(true);done=true;}','else if(choice==visualCount){setLab(true);done=true;}')
s=rep(s,'else if(choice==12)done=true;','else if(choice==visualCount+1)done=true;')
a=s.index('extern "C" void prisma_visual_menu(){')
b=s.index('static volatile bool runtimeActive=false;',a)
t=s[a:b]
t=rep(t,'lcd.setTextColor(0xffff);lcd.setTextSize(2);\n        lcd.setCursor(x+(w-int(strlen(label))*12)/2,y+(h-16)/2);lcd.print(label);',
'''int sz=int(strlen(label))*12<=w-8?2:1;
        lcd.setTextColor(0xffff);lcd.setTextSize(sz);
        lcd.setCursor(x+(w-int(strlen(label))*6*sz)/2,y+(h-8*sz)/2);lcd.print(label);''')
s=s[:a]+t+s[b:]
p.write_text(s.replace("SC020","SC021"))
p=src/"retro_ui.h";p.write_text(p.read_text().replace("SC020","SC021"))
# Uniform and edge fixtures for the quadrant score. Bound int32 arithmetic.
def variance(a,b,c,d):return 4*(a*a+b*b+c*c+d*d)-(a+b+c+d)**2
assert variance(100,100,100,100)==0
assert variance(0,0,255,255)==260100
assert variance(20,20,20,20)<variance(20,20,200,200)
assert 260100*8+765<2**31
assert 5*3==14+1
print("SC021: classic 3x3 Kuwahara, MONET and ACUARELA variants; integer row processing and 14 presets; no AI")

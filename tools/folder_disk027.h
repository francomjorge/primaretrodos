// SC027: synthesize a DOS FAT16 drive from one selected SD directory.
// Volatile sector writes in PSRAM only; no modifications to source files.
// Exact 8.3 names only; reject a tree that cannot be represented losslessly.
#include <dirent.h>
#include <ctype.h>
#include <sys/stat.h>
class FolderDisk final : public Faux86::DiskInterface {
 static constexpr uint32_t sectorSize=512,spc=4,part=63,fatSectors=64,rootSectors=32;
 static constexpr uint32_t diskSectors=65536,partSectors=64*16*63-part;
 static constexpr uint32_t rootStart=part+1+2*fatSectors,dataStart=rootStart+rootSectors;
 static constexpr uint32_t clusters=(part+partSectors-dataStart)/spc;
 static constexpr unsigned maxNodes=512,cacheCount=8,cacheSize=4096,overlayCount=512;
 struct Node {
   char path[256],name[11];
   uint32_t bytes;
   uint16_t parent,slot,children,first,blocks;
   bool dir;
 };
 Node* nodes=nullptr;
 uint16_t* fat=nullptr;
 uint16_t* owner=nullptr;
 unsigned count=1;
 bool valid=false;
 uint64_t pos=0;
 FILE* file=nullptr;
 unsigned fileNode=0;
 struct CacheSlot {uint32_t key=UINT32_MAX;unsigned used=0;};
 CacheSlot cache[cacheCount];
 uint8_t* cacheData=nullptr;
 uint8_t* overlay=nullptr;
 uint32_t overlayTags[overlayCount];
 unsigned overlayUsed=0;
 bool overlayFailed=false;
 char launch[13]={};
 bool carmen=false;
 static bool executable(const Node& n){
   return !n.dir&&(!memcmp(n.name+8,"EXE",3)||!memcmp(n.name+8,"COM",3)||!memcmp(n.name+8,"BAT",3));
 }
 static void filename(const Node& n,char* out){
   unsigned b=0;for(unsigned i=0;i<8&&n.name[i]!=' ';i++)out[b++]=n.name[i];
   out[b++]='.';for(unsigned i=8;i<11&&n.name[i]!=' ';i++)out[b++]=n.name[i];
   out[b]=0;
 }
 void chooseLaunch(const char* path){
   char lower[256];unsigned n=0;
   for(;path[n]&&n<sizeof(lower)-1;n++)lower[n]=tolower((unsigned char)path[n]);
   lower[n]=0;carmen=strstr(lower,"carmen")!=nullptr;
   const char* preferred[]={"PRISMA.BAT","CARMEN.BAT","CARMEN.EXE","CARMEN.COM","WORLD.BAT","WORLD.EXE","WORLD.COM","PRINCE.EXE","PRINCE.COM","START.BAT","PLAY.BAT","RUN.BAT","GAME.BAT"};
   unsigned best=999,chosen=0,unique=0,number=0;
   for(unsigned i=1;i<count;i++){
     if(nodes[i].parent||!executable(nodes[i]))continue;
     char name[13];filename(nodes[i],name);
     Serial.printf("SC031 DOS executable %s\n",name);
     if(strstr(name,"SETUP")||strstr(name,"INSTALL")||strstr(name,"CONFIG")||strstr(name,"UNINST")||strstr(name,"README"))continue;
     unique=i;++number;
     for(unsigned rank=0;rank<sizeof(preferred)/sizeof(*preferred);rank++){
       if(rank>=1&&rank<=6&&!carmen)continue;
       if(!strcmp(name,preferred[rank])&&rank<best){chosen=i;best=rank;}
     }
   }
   if(!chosen&&number==1)chosen=unique;
   if(chosen)filename(nodes[chosen],launch);
   Serial.printf("SC031 DOS launch=%s carmen=%d candidates=%u\n",launch[0]?launch:"MANUAL",carmen,number);
 }
 int overlayFind(uint32_t lba)const{
   for(unsigned i=0;i<overlayUsed;i++)if(overlayTags[i]==lba)return int(i);
   return -1;
 }
 static void put16(uint8_t* p,uint16_t v){p[0]=v;p[1]=v>>8;}
 static void put32(uint8_t* p,uint32_t v){put16(p,v);put16(p+2,v>>16);}
 static bool shortName(const char* in,char* out){
   memset(out,' ',11);
   const char* dot=strchr(in,'.');
   if(dot&&strchr(dot+1,'.'))return false;
   size_t base=dot?size_t(dot-in):strlen(in),ext=dot?strlen(dot+1):0;
   if(!base||base>8||ext>3||(dot&&!ext))return false;
   for(unsigned i=0;i<base+ext;i++){
     unsigned c=(unsigned char)in[i<base?i:i+1];
     if(c>='a'&&c<='z')c-=32;
     if(!((c>='A'&&c<='Z')||(c>='0'&&c<='9')||strchr("!#$%&'()-@^_{}~",c)))return false;
     out[i<base?i:8+i-base]=char(c);
   }
   return true;
 }
 bool walk(unsigned parent,unsigned depth){
   if(depth>6)return false;
   DIR* d=opendir(nodes[parent].path);
   if(!d)return false;
   bool ok=true;
   while(auto* e=readdir(d)){
     const char* name=e->d_name;
     if(!strcmp(name,".")||!strcmp(name,".."))continue;
     if(name[0]=='.'||!strcasecmp(name,"DESKTOP.INI")||!strcasecmp(name,"THUMBS.DB"))continue;
     if(count>=maxNodes){ok=false;break;}
     Node& n=nodes[count];
     if(!shortName(name,n.name)){Serial.printf("SC027 unsupported DOS 8.3 name: %s\n",name);ok=false;break;}
     for(unsigned i=1;i<count;i++)if(nodes[i].parent==parent&&!memcmp(nodes[i].name,n.name,11)){ok=false;break;}
     if(!ok)break;
     int len=snprintf(n.path,sizeof(n.path),"%s/%s",nodes[parent].path,name);
     struct stat st;
     if(len<0||len>=int(sizeof(n.path))||stat(n.path,&st)!=0){ok=false;break;}
     if(!S_ISREG(st.st_mode)&&!S_ISDIR(st.st_mode)){ok=false;break;}
     if(st.st_size<0||uint64_t(st.st_size)>uint64_t(clusters)*spc*512){ok=false;break;}
     n.dir=S_ISDIR(st.st_mode);n.bytes=n.dir?0:st.st_size;
     n.parent=parent;n.slot=nodes[parent].children++;
     unsigned id=count++;
     if(n.dir&&!walk(id,depth+1)){ok=false;break;}
     if((count&15)==0)delay(1);
   }
   closedir(d);return ok;
 }
 void directoryEntry(uint8_t* b,unsigned id){
   const Node& n=nodes[id];memcpy(b,n.name,11);
   b[11]=n.dir?0x10:0x20; // writes redirected to volatile PSRAM overlay
   put16(b+24,0x0021); // valid DOS date: 1980-01-01
   put16(b+26,n.first);put32(b+28,n.bytes);
 }
 void directorySector(uint8_t* b,unsigned id,unsigned sector){
   for(unsigned j=0;j<16;j++){
     unsigned slot=sector*16+j;
     uint8_t* dst=b+j*32;
     if(id&&slot<2){
       memset(dst,' ',11);dst[0]='.';if(slot)dst[1]='.';
       dst[11]=0x10;put16(dst+26,slot?nodes[nodes[id].parent].first:nodes[id].first);
       continue;
     }
     if(id)slot-=2;
     if(slot>=nodes[id].children)continue;
     for(unsigned k=1;k<count;k++)if(nodes[k].parent==id&&nodes[k].slot==slot){directoryEntry(dst,k);break;}
   }
 }
 bool sector(uint32_t lba,uint8_t* b){
   int changed=overlayFind(lba);
   if(changed>=0){memcpy(b,overlay+changed*512,512);return true;}
   memset(b,0,512);
   if(lba==0){
     // Nonbootable MBR; BIOS boots FreeDOS from internal A:. Geometry
     // follows the pinned Faux86 non-active partition fallback (16x63).
     uint8_t* p=b+446;p[1]=1;p[2]=1;p[3]=0;p[4]=0x06;p[5]=15;p[6]=63;p[7]=63;
     put32(p+8,part);put32(p+12,partSectors);b[510]=0x55;b[511]=0xaa;return true;
   }
   if(lba==part){
     b[0]=0xeb;b[1]=0x3c;b[2]=0x90;memcpy(b+3,"PRISMA27",8);
     put16(b+11,512);b[13]=spc;put16(b+14,1);b[16]=2;
     put16(b+17,512);put16(b+19,partSectors);b[21]=0xf8;put16(b+22,fatSectors);
     put16(b+24,63);put16(b+26,16);put32(b+28,part);b[36]=0x80;b[38]=0x29;
     put32(b+39,0x27272727);memcpy(b+43,"PRISMA     ",11);memcpy(b+54,"FAT16   ",8);
     b[510]=0x55;b[511]=0xaa;return true;
   }
   if(lba>part&&lba<rootStart){
     uint32_t offset=((lba-part-1)%fatSectors)*256;
     for(unsigned i=0;i<256&&offset+i<clusters+2;i++)put16(b+i*2,fat[offset+i]);
     return true;
   }
   if(lba>=rootStart&&lba<dataStart){directorySector(b,0,lba-rootStart);return true;}
   if(lba<dataStart||lba>=part+partSectors)return true;
   uint32_t rel=lba-dataStart,cl=rel/spc+2;
   if(cl>=clusters+2)return true;
   unsigned id=owner[cl];if(!id)return true;
   Node& n=nodes[id];
   uint32_t offset=(cl-n.first)*spc+rel%spc;
   if(n.dir){directorySector(b,id,offset);return true;}
   offset*=512;if(offset>=n.bytes)return true;
   uint32_t page=offset/cacheSize,key=(id<<16)|page;
   unsigned slot=(id*17+page)%cacheCount;
   unsigned want=min<uint32_t>(512,n.bytes-offset);
   if(cacheData&&cache[slot].key==key){
     memcpy(b,cacheData+slot*cacheSize+offset%cacheSize,want);++diskHits;return true;
   }
   if(fileNode!=id||!file){if(file)fclose(file);file=fopen(n.path,"rb");fileNode=id;}
   if(!file)return false;
   if(cacheData){
     unsigned bytes=min<uint32_t>(cacheSize,n.bytes-page*cacheSize);
     if(fseek(file,page*cacheSize,SEEK_SET)!=0)return false;
     uint8_t* dst=cacheData+slot*cacheSize;
     cache[slot].key=UINT32_MAX;
     if(fread(dst,1,bytes,file)!=bytes)return false;
     cache[slot].key=key;cache[slot].used=bytes;
     memcpy(b,dst+offset%cacheSize,want);return true;
   }
   return fseek(file,offset,SEEK_SET)==0&&fread(b,1,want,file)==want;
 }
public:
 explicit FolderDisk(const char* path){
   nodes=(Node*)ps_calloc(maxNodes,sizeof(Node));
   fat=(uint16_t*)ps_calloc(clusters+2,sizeof(uint16_t));
   owner=(uint16_t*)ps_calloc(clusters+2,sizeof(uint16_t));
   if(!nodes||!fat||!owner||strlen(path)>=sizeof(nodes[0].path))return;
   strcpy(nodes[0].path,path);nodes[0].dir=true;
   if(!walk(0,0)||!nodes[0].children)return;
   uint32_t next=2;fat[0]=0xfff8;fat[1]=0xffff;
   for(unsigned i=1;i<count;i++){
     Node& n=nodes[i];
     uint32_t bytes=n.dir?(n.children+2)*32:n.bytes;
     uint32_t blocks=(bytes+spc*512-1)/(spc*512);
     if(next+blocks>clusters+2)return;
     n.first=blocks?next:0;n.blocks=blocks;
     for(unsigned j=0;j<blocks;j++){owner[next]=i;fat[next]=j+1==blocks?0xffff:next+1;next++;}
   }
   cacheData=(uint8_t*)ps_calloc(cacheCount,cacheSize);
   chooseLaunch(path);
   valid=true;
   Serial.printf("SC027 FAT16 nodes=%u used_clusters=%u PSRAM_metadata=%u\n",count,next-2,unsigned(maxNodes*sizeof(Node)+4*(clusters+2)));
 }
 ~FolderDisk(){if(file)fclose(file);free(nodes);free(fat);free(owner);free(cacheData);free(overlay);}
 const char* launchCommand()const{return launch;}
 bool isCarmen()const{return carmen;}
 bool isValid() override{return valid;}
 uint64_t getSize() override{return uint64_t(diskSectors)*512;}
 uint64_t seek(uint64_t n) override{pos=min<uint64_t>(n,getSize());return pos;}
 int read(uint8_t* out,unsigned n) override{
   if(!valid)return 0;
   unsigned done=0;uint8_t buf[512];uint32_t start=micros();
   while(done<n&&pos<getSize()){
     if(!sector(pos/512,buf))break;
     unsigned off=pos%512,take=min<unsigned>(n-done,512-off);
     memcpy(out+done,buf+off,take);done+=take;pos+=take;
   }
   ++diskReads;diskReadUs+=micros()-start;return done;
 }
 int write(const uint8_t* in,unsigned count) override{
   if(!valid||!count||pos%512||count%512||pos+count>getSize())return 0;
   if(!overlay)overlay=(uint8_t*)ps_calloc(overlayCount,512);
   if(!overlay)return 0;
   unsigned done=0;
   while(done<count){
     uint32_t lba=pos/512;
     int slot=overlayFind(lba);
     if(slot<0){
       if(overlayUsed>=overlayCount){
         if(!overlayFailed){Serial.println("SC031 DOS temporary write overlay full");overlayFailed=true;}
         break;
       }
       slot=overlayUsed++;overlayTags[slot]=lba;
     }
     memcpy(overlay+slot*512,in+done,512);done+=512;pos+=512;
   }
   return done;
 }
};

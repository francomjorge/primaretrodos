// Legacy PRDOS032 file-backed disk: exact original boot and game bytes.
// Accept either a standalone dosdata partition or a full ESP32 flash image.
// No flash/SD writes, no partition changes.
struct LegacyHeader {char magic[8];uint32_t floppyOffset,floppySize,hardOffset,hardSize;};
static_assert(sizeof(LegacyHeader)==24,"PRDOS032 header");
static uint32_t legacyLE32(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
static bool legacyRead(FILE* f,uint32_t off,void* dst,unsigned n){
 return fseek(f,(long)off,SEEK_SET)==0&&fread(dst,1,n,f)==n;
}
static bool legacyHeader(const char* path,uint32_t& base,LegacyHeader& h){
 struct stat st;
 if(stat(path,&st)||!S_ISREG(st.st_mode)||st.st_size<24||st.st_size>0x7fffffff)return false;
 uint32_t size=st.st_size,limit=size;base=0;
 FILE* f=fopen(path,"rb");if(!f)return false;
 bool ok=legacyRead(f,0,&h,sizeof(h));
 if(!ok||memcmp(h.magic,"PRDOS032",8)){
   ok=false;
   if(size>=0x9000){
     uint8_t entry[32];
     for(unsigned i=0;i<95;i++){
       if(!legacyRead(f,0x8000+i*32,entry,sizeof(entry))||entry[0]!=0xaa||entry[1]!=0x50)break;
       if(entry[2]!=1||memcmp(entry+12,"dosdata",7)||entry[19]!=0)continue;
       base=legacyLE32(entry+4);limit=legacyLE32(entry+8);
       if(base>size||limit>size-base||limit<sizeof(h))break;
       ok=legacyRead(f,base,&h,sizeof(h))&&!memcmp(h.magic,"PRDOS032",8);
       break;
     }
   }
 }
 fclose(f);
 auto inside=[&](uint32_t off,uint32_t n){return off>=sizeof(h)&&n>=512&&!(n%512)&&off<=limit&&n<=limit-off;};
 if(!ok||!inside(h.floppyOffset,h.floppySize)||!inside(h.hardOffset,h.hardSize))return false;
 if(h.floppyOffset<h.hardOffset+h.hardSize&&h.hardOffset<h.floppyOffset+h.floppySize)return false;
 return h.floppySize==1474560||h.floppySize==737280||h.floppySize==1228800||h.floppySize==368640;
}
class LegacyDisk final : public Faux86::DiskInterface {
 FILE* f=nullptr;uint32_t base,len,pos=0;
 static constexpr unsigned blockSize=4096,blocks=32;
 uint8_t* cache=nullptr;
 uint32_t tags[blocks];
public:
 LegacyDisk(const char* path,uint32_t b,uint32_t n):base(b),len(n){
   f=fopen(path,"rb");
   for(auto& t:tags)t=UINT32_MAX;
   if(f)cache=(uint8_t*)ps_malloc(blockSize*blocks);
   Serial.printf("SC030 CLASSIC disk base=%u bytes=%u cache=%u\n",base,len,cache?blockSize*blocks:0);
 }
 ~LegacyDisk(){if(f)fclose(f);free(cache);}
 bool isValid() override{return f&&len;}
 uint64_t getSize() override{return len;}
 uint64_t seek(uint64_t off) override{pos=min<uint64_t>(off,len);return pos;}
 int read(uint8_t* out,unsigned count) override{
   if(!isValid())return 0;
   count=min<uint32_t>(count,len-pos);
   uint32_t start=micros();unsigned done=0;
   while(done<count){
     uint32_t block=pos/blockSize,offset=pos%blockSize,slot=block%blocks;
     unsigned n=min<unsigned>(count-done,blockSize-offset);
     if(cache){
       if(tags[slot]!=block){
         tags[slot]=UINT32_MAX;
         unsigned fill=min<uint32_t>(blockSize,len-block*blockSize);
         if(!legacyRead(f,base+block*blockSize,cache+slot*blockSize,fill))break;
         tags[slot]=block;++diskReads;
       }else ++diskHits;
       memcpy(out+done,cache+slot*blockSize+offset,n);
     }else{
       if(!legacyRead(f,base+pos,out+done,n))break;
       ++diskReads;
     }
     pos+=n;done+=n;
   }
   diskReadUs+=micros()-start;return done;
 }
 int write(const uint8_t*,unsigned) override{return 0;}
};

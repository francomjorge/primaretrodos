#!/usr/bin/env python3
"""Host-test legacy parser and cache against synthetic old flash layouts, not game data."""
from pathlib import Path
import struct,subprocess,tempfile
with tempfile.TemporaryDirectory() as td:
    d=Path(td)
    floppy=bytes(range(256))*5760
    hard=bytes(reversed(range(256)))*32
    raw=bytearray(4096+len(floppy)+len(hard))
    struct.pack_into("<8sIIII",raw,0,b"PRDOS032",4096,len(floppy),4096+len(floppy),len(hard))
    raw[4096:4096+len(floppy)]=floppy
    raw[4096+len(floppy):]=hard
    (d/"raw.bin").write_bytes(raw)
    full=bytearray(b"\xff"*(16*1024*1024))
    struct.pack_into("<HBBII16sI",full,0x8000,0x50aa,1,0x40,0x700000,0x900000,b"dosdata",0)
    full[0x700000:0x700000+len(raw)]=raw
    (d/"full.bin").write_bytes(full)
    bad=bytearray(raw)
    struct.pack_into("<I",bad,20,0xffffffff)
    (d/"bad.bin").write_bytes(bad)
    cpp=r'''
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <sys/stat.h>
using std::min;
static void* ps_malloc(size_t n){return malloc(n);}
static unsigned micros(){return 0;}
static unsigned diskReads=0,diskHits=0,diskReadUs=0;
struct Log{template<class... T> void printf(const char* f,T... t){std::printf(f,t...);}} Serial;
namespace Faux86{
struct DiskInterface{
virtual ~DiskInterface()=default;
virtual bool isValid()=0;
virtual uint64_t getSize()=0;
virtual uint64_t seek(uint64_t)=0;
virtual int read(uint8_t*,unsigned)=0;
virtual int write(const uint8_t*,unsigned)=0;
};}
#include "legacy_disk030.h"
int main(int argc,char** argv){
 for(int i=1;i<=2;i++){
   uint32_t base=0;LegacyHeader h{};
   if(!legacyHeader(argv[i],base,h)||base!=(i==1?0:0x700000))return 1;
   LegacyDisk disk(argv[i],base+h.hardOffset,h.hardSize);
   if(!disk.isValid()||disk.getSize()!=8192)return 2;
   uint8_t buf[1024];
   disk.seek(3900);
   if(disk.read(buf,1024)!=1024)return 3;
   for(int j=0;j<1024;j++)if(buf[j]!=255-((3900+j)%256))return 4;
   disk.seek(3900);
   if(disk.read(buf,1024)!=1024||!diskHits)return 5;
   if(disk.write(buf,512)!=0)return 6;
 }
 uint32_t base;LegacyHeader h{};
 if(legacyHeader(argv[3],base,h))return 7;
 return 0;
}
'''
    (d/"test.cpp").write_text(cpp)
    subprocess.run(["g++","-std=c++17","-I"+str(Path(__file__).parent.resolve()),str(d/"test.cpp"),"-o",str(d/"test")],check=True)
    subprocess.run([str(d/"test"),str(d/"raw.bin"),str(d/"full.bin"),str(d/"bad.bin")],check=True)
print("SC030: raw PRDOS032/full flash partition lookup, bounded reads, cross-cache-block exact bytes, invalid sizes rejected")

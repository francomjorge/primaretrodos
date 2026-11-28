#!/usr/bin/env python3
"""Host check of exact target FAT16 adapter using mtools, with no firmware stubs in target."""
from pathlib import Path
import tempfile,subprocess,hashlib
header=Path(__file__).with_name("folder_disk027.h").resolve()
with tempfile.TemporaryDirectory() as td:
    d=Path(td);g=d/"game";g.mkdir();(g/"DATA").mkdir()
    (g/"GAME.EXE").write_bytes(bytes(range(256))*19)
    (g/"DATA"/"LEVEL.DAT").write_bytes(b"PRISMA"*999)
    (g/"EMPTY.TXT").touch()
    cpp=r'''
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <strings.h>
using std::min;
static unsigned micros(){return 0;}
static void delay(unsigned){}
static void* ps_calloc(size_t n,size_t size){return calloc(n,size);}
struct SerialStub{template<class... T> void printf(const char* f,T... t){std::printf(f,t...);}} Serial;
static unsigned diskReads=0,diskReadUs=0,diskHits=0;
namespace Faux86 {
struct DiskInterface{
virtual ~DiskInterface()=default;
virtual bool isValid()=0;
virtual uint64_t getSize()=0;
virtual uint64_t seek(uint64_t)=0;
virtual int read(uint8_t*,unsigned)=0;
virtual int write(const uint8_t*,unsigned)=0;
};}
#include "folder_disk027.h"
int main(int argc,char**argv){
 FolderDisk disk(argv[1]);
 if(!disk.isValid())return 1;
 FILE* out=fopen(argv[2],"wb");
 if(!out)return 2;
 uint8_t buf[4096];
 while(auto n=disk.read(buf,sizeof(buf)))if(fwrite(buf,1,n,out)!=unsigned(n))return 3;
 if(ftell(out)!=disk.getSize())return 4;
 fclose(out);
 if(strcmp(disk.launchCommand(),"GAME.EXE"))return 5;
 if(!diskHits)return 6;
 disk.seek(512);memset(buf,0x5a,512);
 if(disk.write(buf,512)!=512)return 7;
 disk.seek(512);memset(buf,0,512);
 if(disk.read(buf,512)!=512)return 8;
 for(unsigned i=0;i<512;i++)if(buf[i]!=0x5a)return 9;
 FolderDisk fresh(argv[1]);fresh.seek(512);
 if(fresh.read(buf,512)!=512||buf[0]!=0)return 10;
 return 0;
}
'''
    (d/"test.cpp").write_text(cpp)
    subprocess.run(["g++","-std=c++17","-O2","-I"+str(header.parent),str(d/"test.cpp"),"-o",str(d/"test")],check=True)
    img=d/"game.img"
    subprocess.run([str(d/"test"),str(g),str(img)],check=True)
    assert img.stat().st_size==32*1024*1024
    spec=str(img)+"@@"+str(63*512)
    subprocess.run(["mdir","-i",spec,"::/"],check=True)
    for path in ("GAME.EXE","DATA/LEVEL.DAT","EMPTY.TXT"):
        target=d/("check-"+Path(path).name)
        subprocess.run(["mcopy","-i",spec,"::/"+path,str(target)],check=True)
        assert target.read_bytes()==(g/path).read_bytes(),path
    (g/"LONGFILENAME.TXT").touch()
    assert subprocess.run([str(d/"test"),str(g),str(img)]).returncode==1
print("SC027 FAT16: MBR/BPB, nested file, multi-cluster file, empty file, exact bytes, launch detection, cache hits, volatile writes and unchanged original, invalid 8.3 rejected")

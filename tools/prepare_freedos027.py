#!/usr/bin/env python3
"""Create an internal boot floppy from the official FreeDOS 1.4 distribution.
Only the boot configuration changes; no proprietary MS-DOS image is bundled.
"""
from pathlib import Path
import hashlib,os,subprocess,sys,tempfile,zipfile
root=Path(sys.argv[1]).resolve()
archive=Path(sys.argv[2])
with zipfile.ZipFile(archive) as z:
    names=[n for n in z.namelist() if n.lower().endswith("144m/x86boot.img")]
    assert len(names)==1,names
    original=z.read(names[0])
assert len(original)==1474560 and original[510:512]==b"\x55\xaa"
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp); img=d/"boot.img";img.write_bytes(original)
    def run(*args):
        return subprocess.check_output([*args],stderr=subprocess.STDOUT).decode(errors="replace")
    def mdir():
        return run("mdir","-i",str(img),"-b","-s","::/").splitlines()
    paths=mdir()
    print("FreeDOS original paths:",paths)
    assert any(n.rstrip("/").upper()=="::/KERNEL.SYS" for n in paths),"root KERNEL.SYS absent"
    cmd=[n for n in paths if n.rstrip("/").upper().endswith("/COMMAND.COM")]
    assert cmd,"COMMAND.COM absent"
    if not any(n.upper()=="::/COMMAND.COM" for n in cmd):
        run("mcopy","-i",str(img),cmd[0],str(d/"COMMAND.COM"))
        run("mcopy","-o","-i",str(img),str(d/"COMMAND.COM"),"::/COMMAND.COM")
    config=b"FILES=30\r\nBUFFERS=10\r\nLASTDRIVE=E\r\nSHELL=A:\\COMMAND.COM /P=A:\\AUTOEXEC.BAT\r\n"
    auto=b"@ECHO OFF\r\nECHO PRISMA DOS - SD GAME\r\nC:\r\n"
    for name,data in [("FDCONFIG.SYS",config),("CONFIG.SYS",config),("AUTOEXEC.BAT",auto),("FDAUTO.BAT",auto)]:
        p=d/name;p.write_bytes(data);run("mcopy","-o","-i",str(img),str(p),"::/"+name)
        check=d/("check-"+name)
        run("mcopy","-i",str(img),"::/"+name,str(check))
        assert check.read_bytes()==data
    binary=img.read_bytes()
    assert len(binary)==len(original) and binary[:512]==original[:512]
p=root/"src/freedos_boot027.h"
with p.open("w") as f:
    f.write("#pragma once\n#include <stdint.h>\nstatic const uint8_t prismaFreeDOSBoot[]={\n")
    for i in range(0,len(binary),32):
        f.write(",".join(f"0x{x:02x}" for x in binary[i:i+32])+",\n")
    f.write("};\n")
(root/"tools/freedos027-origin.txt").write_text("FreeDOS 1.4 official Floppy Edition\nhttps://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/distributions/1.4/\nOriginal archive SHA256 "+hashlib.sha256(archive.read_bytes()).hexdigest()+"\nOriginal image SHA256 "+hashlib.sha256(original).hexdigest()+"\nConfigured boot SHA256 "+hashlib.sha256(binary).hexdigest()+"\nOnly CONFIG.SYS/FDCONFIG.SYS and startup batch changed; COMMAND.COM copied to root if needed.\nFreeDOS source packages: https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/repositories/1.4/\n")
print("SC027 internal FreeDOS boot image bytes:",len(binary))

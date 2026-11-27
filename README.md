# PRISMA SCUMM — SC001

Experimental native SCUMM/Cine port for Guition ESP32-4848S040C (ESP32-S3 N16R8). Upstream: https://github.com/fcipaq/scummvm_esp32 at c8053f4b606ec29ad7da2243b107e8941c9afd41, GPL-licensed upstream files retain their notices. ESP-IDF 5.2.1. No x86, NES or GB.

Target: ST7701 RGB 480x480, GT911 I2C SDA19/SCL45, SD SPI SCK48 MOSI47 MISO41 CS42. LCD command SPI CS39. Backlight GPIO38. Audio output disabled (GPIO11 is LCD data; avoid relay GPIO1/2/40).

SC001 is experimental until compilation and physical testing. Game assets are not distributed. Use legally obtained Monkey Island files on FAT32 SD at /roms/scummvm/monkey1/ (MONKEY1.000 and MONKEY1.001, appropriate edition). Preserve a backup of existing flash before full installation.

Build patches and workflow will be tracked in this repository. No claim of physical compatibility or performance until tested.

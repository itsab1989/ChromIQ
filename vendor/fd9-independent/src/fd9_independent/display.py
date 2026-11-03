# SPDX-License-Identifier: GPL-3.0-or-later
"""Original monochrome instrument artwork, generated without vendor assets."""
import struct

WIDTH, HEIGHT = 320, 352
# Hand-authored five-by-seven glyphs. No system fonts or bitmap fixtures.
FONT = {
 'A':('01110','10001','10001','11111','10001','10001','10001'),
 'C':('01111','10000','10000','10000','10000','10000','01111'),
 'E':('11111','10000','10000','11110','10000','10000','11111'),
 'G':('01111','10000','10000','10111','10001','10001','01110'),
 'H':('10001','10001','10001','11111','10001','10001','10001'),
 'I':('11111','00100','00100','00100','00100','00100','11111'),
 'L':('10000','10000','10000','10000','10000','10000','11111'),
 'M':('10001','11011','10101','10101','10001','10001','10001'),
 'N':('10001','11001','11001','10101','10011','10011','10001'),
 'P':('11110','10001','10001','11110','10000','10000','10000'),
 'R':('11110','10001','10001','11110','10100','10010','10001'),
 'S':('01111','10000','10000','01110','00001','00001','11110'),
 'T':('11111','00100','00100','00100','00100','00100','00100'),
 'U':('10001','10001','10001','10001','10001','10001','01110'),
 'W':('10001','10001','10001','10101','10101','10101','01010'),
 ' ':('00000',)*7,
}


def raster(kind):
    if kind not in (1,3):raise ValueError('Supported screens are insertion and acquisition')
    pixels=bytearray(b'\xff'* (WIDTH*HEIGHT))
    def rectangle(x0,y0,x1,y1):
        for y in range(max(0,y0),min(HEIGHT,y1)):
            pixels[y*WIDTH+max(0,x0):y*WIDTH+min(WIDTH,x1)]=b'\0'*max(0,min(WIDTH,x1)-max(0,x0))
    def text(label,y,scale=3):
        x=(WIDTH-(len(label)*6-1)*scale)//2
        for character in label:
            for gy,row in enumerate(FONT[character]):
                for gx,bit in enumerate(row):
                    if bit=='1':rectangle(x+gx*scale,y+gy*scale,x+(gx+1)*scale,y+(gy+1)*scale)
            x+=6*scale
    text('INSERT CHART' if kind==1 else 'MEASURING',30)
    # Original sheet outline and a large upward feed arrow.
    rectangle(72,112,248,116);rectangle(72,288,248,292)
    rectangle(72,116,76,288);rectangle(244,116,248,288)
    if kind==1:
        rectangle(151,173,169,253)
        for y in range(142,181):
            half=y-142;rectangle(160-half,y,160+half+1,y+1)
    else:
        for y in (154,193,232):rectangle(104,y,216,y+10)
        text('PLEASE WAIT',316,2)
    return bytes(pixels)


def chunks(kind):
    """Serialize observed control fields with newly generated pixel words.

    DEFAULT is an observed protocol screen identifier, not a copied bitmap.
    Only black/white 16-bit pixels are used; their byte order is unambiguous.
    This original artwork has been used in supervised single-unit acquisitions.
    """
    bitmap=b''.join(b'\xff\xff' if p else b'\0\0' for p in raster(kind))
    result=[]
    for index,start in enumerate(range(0,len(bitmap),8000)):
        metadata=struct.pack('<II8s12I',5,kind,b'DEFAULT\0',*([0]*11),index)
        result.append(metadata+bitmap[start:start+8000])
    return tuple(result)


def write_preview(path,kind=1):
    from pathlib import Path
    with Path(path).open('xb') as output:
        output.write(f'P5\n{WIDTH} {HEIGHT}\n255\n'.encode()+raster(kind))

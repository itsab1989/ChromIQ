# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent geometry for four isolated square marks; no colour recognition.

This deliberately narrow detector supports the printed OpenRIP grid. Symmetric
marks cannot determine colour order; returned rows are sensor-X ordered only.
"""
import math


def find_marks(pixels,width,height):
    if width<100 or height<100 or len(pixels)!=width*height:
        raise ValueError('Invalid grayscale image dimensions')
    step=4;cw=(width+step-1)//step;ch=(height+step-1)//step
    dark=set()
    for y in range(0,height,step):
        for x in range(0,width,step):
            if pixels[y*width+x]<65:dark.add((y//step)*cw+x//step)
    candidates=[]
    while dark:
        seed=dark.pop();stack=[seed];component=[]
        while stack:
            p=stack.pop();component.append(p);x=p%cw;y=p//cw
            for q in ((p-1 if x else -1),(p+1 if x+1<cw else -1),p-cw,p+cw):
                if q in dark:dark.remove(q);stack.append(q)
        xs=[p%cw for p in component];ys=[p//cw for p in component]
        x0=min(xs)*step;y0=min(ys)*step
        bw=(max(xs)-min(xs)+1)*step;bh=(max(ys)-min(ys)+1)*step
        if not (25<=bw<=65 and 25<=bh<=65 and .7<bw/bh<1.4 and len(component)*step*step/(bw*bh)>.65):continue
        coords=[(x,y) for y in range(max(0,y0-step),min(height,y0+bh+step)) for x in range(max(0,x0-step),min(width,x0+bw+step)) if pixels[y*width+x]<65]
        candidates.append((sum(x for x,y in coords)/len(coords),sum(y for x,y in coords)/len(coords)))
    if len(candidates)!=4:raise ValueError(f'Expected exactly four isolated square marks, found {len(candidates)}')
    top=sorted(sorted(candidates,key=lambda p:p[1])[:2]);bottom=sorted(sorted(candidates,key=lambda p:p[1])[2:])
    tl,tr=top;bl,br=bottom
    sx1=tr[0]-tl[0];sx2=br[0]-bl[0];sy1=bl[1]-tl[1];sy2=br[1]-tr[1]
    if min(sx1,sx2,sy1,sy2)<100 or abs(sx1/sx2-1)>.03 or abs(sy1/sy2-1)>.03:
        raise ValueError('Marks do not form a consistent chart rectangle')
    if max(abs(tr[1]-tl[1]),abs(br[1]-bl[1]))>sx1*.05 or max(abs(bl[0]-tl[0]),abs(br[0]-tr[0]))>sy1*.05:
        raise ValueError('Chart skew exceeds supported geometry')
    return [tl,tr,bl,br]


def grid_rows(marks,x_mm,y_mm,mark_span_mm=(118,235),mark_origin_mm=(9.5,32.5),mirrored_image=False,image_width_px=None):
    """Bind physical grid coordinates to four image marks.

    Historical default returns image-X coordinates. Explicit mirrored_image
    maps a mirrored chart image to the hypothesized instrument-X convention:
    physical X interpolates right-to-left in the image, then command X is
    image_width_px minus image X. This opt-in needs live position validation;
    it is not inferred from symmetric fiducials or spectral color labels.
    """
    if len(marks)!=4 or not 1<=len(x_mm)<=64 or not 1<=len(y_mm)<=128:raise ValueError('Require four marks, 1..64 columns and 1..128 rows')
    sx,sy=mark_span_mm;ox,oy=mark_origin_mm
    values=[v for p in marks for v in p]+list(x_mm)+list(y_mm)+[sx,sy,ox,oy]
    if not all(math.isfinite(v) for v in values) or sx<=0 or sy<=0:raise ValueError('Invalid geometry values')
    if any(a>=b for a,b in zip(x_mm,x_mm[1:])) or any(a>=b for a,b in zip(y_mm,y_mm[1:])):raise ValueError('Grid axes must increase')
    if not all(0<(x-ox)/sx<1 for x in x_mm) or not all(0<(y-oy)/sy<1 for y in y_mm):raise ValueError('Grid must lie within the marks')
    if not isinstance(mirrored_image,bool):raise ValueError('Mirrored-image convention must be explicit boolean')
    if mirrored_image and (not isinstance(image_width_px,int) or isinstance(image_width_px,bool) or image_width_px<100 or any(not 0<=p[0]<image_width_px for p in marks)):
        raise ValueError('Mirrored-image mapping requires a valid complete image width')
    if not mirrored_image and image_width_px is not None:raise ValueError('Image width supplied without mirrored-image mapping')
    tl,tr,bl,br=marks;rows=[]
    for y in y_mm:
        v=(y-oy)/sy;left=[tl[i]*(1-v)+bl[i]*v for i in range(2)];right=[tr[i]*(1-v)+br[i]*v for i in range(2)]
        row=[]
        for x in x_mm:
            u=(x-ox)/sx
            if mirrored_image:u=1-u
            point=[left[i]+(right[i]-left[i])*u for i in range(2)]
            if mirrored_image:point[0]=image_width_px-point[0]
            row.append(point)
        rows.append(row)
    return rows

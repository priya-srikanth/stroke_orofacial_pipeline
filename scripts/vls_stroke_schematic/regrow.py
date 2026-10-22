import pickle, sys, numpy as np
sys.path.insert(0,'/home/claude/widefield_pipeline'); sys.path.insert(0,'.')
from scipy import ndimage as ndi
from wfield_local.histology_map.sections import rasterize
from grow import grow
D=pickle.load(open('prep2.pkl','rb'))
for k,d in D.items():
    T=d['T']; sh=d['stroke'].shape; x0=T['x0']; tm=T['tissue']
    xs=np.arange(sh[1])[None,:]; xm=np.clip(np.round(2*x0-xs).astype(int),0,sh[1]-1)[0]
    frame=ndi.binary_dilation(ndi.binary_fill_holes(tm[:,xm]&(xs<x0)) | ndi.binary_fill_holes(tm&(xs<x0)),iterations=6)   # either side's tissue: shredded contra left no lateral room
    left=(xs<x0)&np.ones(sh,bool)
    seed=rasterize(d['gl'],sh) if d['gl'] is not None else np.zeros(sh,bool)
    surv=rasterize(T['gi'],sh)&~seed; mcm=rasterize(d['mirror'],sh)
    if not seed.any(): seed=mcm&~surv&left
    stri=ndi.binary_dilation(rasterize(T['gi'],sh)|seed,iterations=10)   # Priya 10-21: lateral edge stops at the striatum's own lateral border (corpus callosum / external capsule): ipsi striatal territory + ~50 um, not the mirrored contra
    dom=((mcm&~surv)|seed)&frame&left&stri; fb=frame&left&stri   # Priya 10-21: a blob may cover surviving-looking striatum; excluding it made ventral crescents
    yb=np.nonzero(seed.any(1))[0].max()+29 if seed.any() else sh[0]   # Priya: only 'a touch' ventral of the stroke (~150 um)
    yy_=np.arange(sh[0])[:,None]; dom=dom&(yy_<=yb); fb=fb&(yy_<=yb)
    s=grow(seed,dom,fb,d['target_px']); d['stroke']=s
    d['flags']=[f for f in d['flags'] if not f.startswith('footprint')]
    if s.sum()<0.9*d['target_px']: d['flags'].append(f"footprint {s.sum()/d['target_px']:.0%} of lost area")
    print(k, round(s.sum()/max(d['target_px'],1),2), d['flags'], flush=True)
pickle.dump(D,open('prep4.pkl','wb'))

import sys, os, time
from multiprocessing import Pool
sys.path.insert(0, os.path.expanduser('~/hist'))
import build
C = os.path.expanduser('~/hist/L6')
def one(pk):
    if os.path.exists(f"{C}/{pk.replace(':', '_')}_L5.npz"): return None
    try: build.level_img(pk, 5, C); return pk
    except Exception as e: return 'FAIL ' + pk + ' ' + str(e)[:80]
if __name__ == '__main__':
    t = time.time(); todo = open(os.path.expanduser('~/hist/new_keep.txt')).read().split()
    with Pool(6) as p:
        for r in p.imap_unordered(one, todo):
            if r: print(r, round(time.time() - t), flush=True)
            if time.time() - t > 150: break
    print('left', sum(not os.path.exists(f"{C}/{k.replace(':', '_')}_L5.npz") for k in todo))

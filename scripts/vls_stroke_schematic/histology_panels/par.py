import sys, os, json, time
from multiprocessing import Pool
sys.path.insert(0, os.path.expanduser('~/hist'))
import build
O = sys.argv[1]; jobs = json.load(open(os.path.expanduser('~/hist/jobs_final.json')))
def one(j):
    f = f"{O}/rec_{j['pick'].replace(':', '_')}.json"
    if os.path.exists(f): return None
    r = build.build(j, O, os.path.expanduser('~/hist/L6')); json.dump(r, open(f, 'w')); return j['pick']
if __name__ == '__main__':
    t = time.time(); done = set(json.load(open(f'{O}/manifest.json'))) if os.path.exists(f'{O}/manifest.json') else set()
    todo = [j for j in jobs if j['pick'] not in done and not os.path.exists(f"{O}/rec_{j['pick'].replace(':', '_')}.json")]
    with Pool(6) as p:
        for r in p.imap_unordered(one, todo[:int(sys.argv[2])]):
            print(r, round(time.time() - t), flush=True)
            if time.time() - t > 150: break
    print('remaining', len(todo) - int(sys.argv[2]))

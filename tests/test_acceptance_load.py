import cv2, os, sys, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from linework.split import find_icons, crop_icon
from linework.pipeline import Options, process_icon

def busy_loop(stop_ev):
    x = 0
    while not stop_ev.is_set():
        x = (x * 1103515245 + 12345) & 0x7fffffff

if __name__ == '__main__':
    from linework.trace import ink_map
    g = cv2.imread(r'samples/home-icons.png', 0)
    D = ink_map(g)
    w, icons, lab = find_icons(D)
    crop, _ = crop_icon(g, lab, icons[2], pad=12, bg=255)
    print(f"Testing on icon 3 (crop shape {crop.shape})")

    print("--- 1. Running ALONE ---")
    t0 = time.time()
    r_alone = process_icon(crop, Options(quality='standard'), name='alone')['metrics']
    t_alone = time.time() - t0
    print(f"Alone:  IoU = {r_alone['iou']:.5f}, paths = {r_alone['paths']}, nodes = {r_alone['nodes']}, wall_time = {t_alone:.2f}s")

    n_cpus = mp.cpu_count()
    print(f"--- 2. Running LOADED ({n_cpus} CPU busy workers) ---")
    stop_ev = mp.Event()
    procs = [mp.Process(target=busy_loop, args=(stop_ev,)) for _ in range(n_cpus)]
    for p in procs:
        p.start()

    try:
        t0 = time.time()
        r_load = process_icon(crop, Options(quality='standard'), name='loaded')['metrics']
        t_load = time.time() - t0
    finally:
        stop_ev.set()
        for p in procs:
            p.join(timeout=2)

    print(f"Loaded: IoU = {r_load['iou']:.5f}, paths = {r_load['paths']}, nodes = {r_load['nodes']}, wall_time = {t_load:.2f}s")

    print("\n--- COMPARISON ---")
    print(f"Alone:  IoU {r_alone['iou']:.5f} | paths {r_alone['paths']} | nodes {r_alone['nodes']} | wall {t_alone:.2f}s")
    print(f"Loaded: IoU {r_load['iou']:.5f} | paths {r_load['paths']} | nodes {r_load['nodes']} | wall {t_load:.2f}s")

    assert abs(r_alone['iou'] - r_load['iou']) < 1e-6, f"IoU diff: {r_alone['iou']} vs {r_load['iou']}"
    assert r_alone['paths'] == r_load['paths'], "Paths mismatch"
    assert r_alone['nodes'] == r_load['nodes'], "Nodes mismatch"
    print("ACCEPTANCE TEST PASSED: Quality is 100% consistent regardless of CPU load!")

import cv2
import numpy as np
from linework.pipeline import process_icon, Options
from linework.doctor import Doctor, ink_of

img1_path = r"C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/media_1794413204434_39e37077.png"
img2_path = r"C:/Users/USER/.gemini/antigravity/brain/970fe8ba-3395-424d-a702-a938d367e356/.user_uploaded/media_1794413245794_8d987e7d.png"

def test_cap():
    print("=== TESTING GRADUATION CAP FIX ===")
    img = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
    opts = Options(fresh=True, memory=False, quality='standard', joins=True, decision=True)
    res = process_icon(img, opts, name='cap_verified')
    m = res['model']
    
    # Check diamond path
    diamond_paths = [p for p in m.paths if any(40 < pt[0] < 70 and 85 < pt[1] < 105 for pt in p.A)]
    print(f"Diamond paths found: {len(diamond_paths)}")
    for dp in diamond_paths:
        print(f"  Path w={dp.w:.2f}, closed={dp.closed}, len(A)={len(dp.A)}, join={dp.join}")
        # check left and right apexes
        has_left = any(np.linalg.norm(pt - [54.0, 95.0]) < 8.0 for pt in dp.A)
        has_right = any(np.linalg.norm(pt - [264.0, 94.0]) < 8.0 for pt in dp.A)
        print(f"  Has left apex: {has_left}, Has right apex: {has_right}")

    doc = Doctor((255 - img) / 255.0)
    iou = doc.iou(ink_of(m))
    print(f"Cap IoU: {iou*100:.2f}%")

    with open("verified_cap_fixed.svg", "w") as f:
        f.write(m.svg())
    ink = (255 * (1.0 - ink_of(m))).astype(np.uint8)
    cv2.imwrite("verified_cap_fixed.png", ink)
    print("Saved verified_cap_fixed.svg and verified_cap_fixed.png")

def test_whiteboard():
    print("\n=== TESTING WHITEBOARD FRAME SAG FIX ===")
    img = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
    opts = Options(fresh=True, memory=False, quality='standard', joins=True, decision=True)
    res = process_icon(img, opts, name='board_verified')
    m = res['model']

    p7 = m.paths[7]
    print(f"Frame Path: closed={p7.closed}, len(A)={len(p7.A)}")
    bottom_nodes = []
    for idx, pt in enumerate(p7.A):
        if 185 < pt[1] < 205:
            bottom_nodes.append((idx, pt[0], pt[1]))
            print(f"   Node {idx}: x={pt[0]:.2f}, y={pt[1]:.2f}")

    # Check max dip along bottom nodes
    ys = [pt[2] for pt in bottom_nodes]
    max_y_span = max(ys) - min(ys)
    print(f"Bottom frame y span: {max_y_span:.2f}px (target < 1.0px)")

    doc = Doctor((255 - img) / 255.0)
    iou = doc.iou(ink_of(m))
    print(f"Whiteboard IoU: {iou*100:.2f}%")

    with open("verified_whiteboard_fixed.svg", "w") as f:
        f.write(m.svg())
    ink = (255 * (1.0 - ink_of(m))).astype(np.uint8)
    cv2.imwrite("verified_whiteboard_fixed.png", ink)
    print("Saved verified_whiteboard_fixed.svg and verified_whiteboard_fixed.png")

if __name__ == "__main__":
    test_cap()
    test_whiteboard()

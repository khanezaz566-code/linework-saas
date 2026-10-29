import cv2, json

orig = cv2.imread("data/225b51e61676/original.png", 0)
with open("data/225b51e61676/job.json") as f:
    job = json.load(f)

box = job['icons'][5]['box']
crop = orig[box[1]:box[3], box[0]:box[2]]
cv2.imwrite("scratch/icon5_crop.png", crop)
print("Saved scratch/icon5_crop.png, shape:", crop.shape)

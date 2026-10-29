import json, os, glob
import cv2

for jid in ['225b51e61676', '4d5d81238877', '0a2b06637601']:
    p = f'data/{jid}/original.png'
    img = cv2.imread(p)
    print(jid, "original shape:", img.shape)

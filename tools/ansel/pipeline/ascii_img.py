import sys
import imageio.v3 as iio
import numpy as np

img = iio.imread(sys.argv[1])
h, w, c = img.shape
img_gray = np.mean(img, axis=2)

chars = " .:-=+*#%@"
out = ""
for y in range(0, h, h//20):
    for x in range(0, w, w//60):
        val = int(img_gray[y, x] / 255.0 * 9.99)
        out += chars[val]
    out += "\n"
print(out)

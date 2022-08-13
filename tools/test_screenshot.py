import glob
import os
import subprocess
from itertools import product, combinations
from PIL import Image

import cv2

DIRNAME = "./photos"
DELAY = 3
WIDTH = 1920
HEIGHT = 1080

# cv2 auto-delay
# Amount of bars corresponds to amount of test pixels
BARS = 8
# Amount of pixels that can be wrong before search is stopped
WRONG_LIMIT = 1  # min = 0, max = BARS - 1
BAR_WIDTH = WIDTH // BARS

# since bars are vertical, all rows should be the same during rainbow bars
TEST_ROW = HEIGHT // 2


def generate_test_pixels(frame, bar_width, test_row):
    pixels = []

    for b in range(BARS):
        # middle column of bar
        test_col = (b * bar_width) + (bar_width // 2)
        # actual pixel color value
        pixels.append(frame.item(test_row, test_col, 0))

    return pixels


# create photo directory
if not os.path.exists(DIRNAME):
    os.makedirs(DIRNAME)
    print("Created directory")

# cv2 screenshots
cam = cv2.VideoCapture()
cam.open(0)
input_types = "MJPG", "YUYV"
output_types = "png", "jpg"
for inp, out in product(input_types, output_types):
    cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*inp))
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    if cam.isOpened():

        still_looking = True
        count = 0
        wrong_count = 0

        ret, iframe = cam.read()
        test_pixels = generate_test_pixels(iframe, BAR_WIDTH, TEST_ROW)

        while (still_looking):
            count += 1  # frame counter

            ret, frame = cam.read()  # get frame

            for b in range(0, BARS):
                # middle column of bar
                test_col = (b * BAR_WIDTH) + (BAR_WIDTH // 2)

                # actual pixel color value
                actual = frame.item(TEST_ROW, test_col, 0)

                # expected pixel color value
                expected = test_pixels[b]

                # stop search and save photo if colors do not match rainbow-bar
                if (actual != expected):
                    wrong_count += 1
                    if wrong_count > WRONG_LIMIT:
                        # save screenshot
                        cv2.imwrite(f"{DIRNAME}/cv2_{inp}.{out}", frame)
                        print(f"cv2 {inp} {out}")
                        still_looking = False
                        break

    # time.sleep(0.25)
cam.release()

# ffmpeg screenshots
input_types = "mjpeg", "yuyv422"
output_types = "png", "jpg"
for inp, out in product(input_types, output_types):
    try:
        cmd = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner", "-y",
                "-f", "v4l2",
                "-input_format", f"{inp}",
                "-video_size", f"{WIDTH}x{HEIGHT}",
                "-i", "/dev/video0",
                "-ss", f"{DELAY}",
                "-vframes", "1",
                f"{DIRNAME}/ffmpeg_{inp}.{out}"
            ],
            cwd=".",
            check=True,
            capture_output=True
        )
        print(f"ffmpeg {inp} {out}")
    except subprocess.CalledProcessError as exc:
        print(exc)

# Analyze
files = glob.glob(f'{DIRNAME}/*')
print(files, "\n")
images = []
for name in files:
    im = cv2.imread(name)
    images.append(im)
    # display(Image.fromarray(im))
for (idx0, im0), (idx1, im1) in combinations(enumerate(images), 2):
    delta = (((im0.astype(float)/255 - im1.astype(float)/255)**2).mean())**.5
    print(f"{files[idx0]} {files[idx1]} - {delta}")

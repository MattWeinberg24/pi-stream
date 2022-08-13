"""Fast Screenshot Mode Thread Controller"""

import queue
import threading
import cv2
from loguru import logger


class FastScreenshotReader(threading.Thread):

    """Fast Screenshot Mode Thread Controller"""
    def __init__(self,
                 inp_fmt: str, out_fmt: str,
                 width: int, height: int,
                 device: str = "/dev/video0"):
        super(FastScreenshotReader, self).__init__()

        self.inp_fmt = "MJPG" if inp_fmt == "jpg" else "YUYV"
        self.out_fmt = out_fmt
        self.width = width
        self.height = height
        self.device = device

        self.cam = cv2.VideoCapture()
        self.q = queue.Queue()
        self.read_frame = False

        self.lock = threading.Lock()

    def run(self):
        logger.debug("Running Thread")

        self.cam.open(self.device)

        fourcc = cv2.VideoWriter_fourcc(*self.inp_fmt)
        self.cam.set(cv2.CAP_PROP_FOURCC, fourcc)

        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        while True:
            # try:
            frame = self.cam.read()[1]
            if frame is None:
                break

            if self.read_frame:
                self.q.put(frame)
                logger.success("Pushed Frame")

                self.read_frame = False

        logger.debug("Stopped Thread")

    def stop(self):
        """Causes frame-loop to end, therefore ending the thread"""
        logger.debug("Stopping Thread")
        self.cam.release()
        return {
            "success": True
        }

    def get_frame(self):
        """Saves the most recent frame read by the frame-loop"""

        with self.lock:
            self.read_frame = True
            frame = self.q.get()  # blocks until frame is available
            return {
                "success": True,
                "data": cv2.imencode(f".{self.out_fmt}", frame)[1].tobytes(),
                "format": self.out_fmt
            }

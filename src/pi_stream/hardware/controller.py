"""Hardware Controller"""

# builtin
import datetime
from enum import Enum
import os
import time

# pip
import cv2
from loguru import logger
import numpy as np
import sh
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from usb.core import find as findusb

# custom
from fast_screenshot_reader import FastScreenshotReader
from util import force_stop, force_exists, video_length
from recording import Recording


class ControllerErrorCode(str, Enum):
    SUCCESS = 'SUCCESS'

    INVALID_STATE = 'INVALID_STATE'

    # parameters
    INVALID_PROCESS = 'INVALID_PROCESS'
    INVALID_FORMAT = 'INVALID_FORMAT'
    INVALID_FILENAME = 'INVALID_FILENAME'

    COMMAND_ERROR = 'COMMAND_ERROR'  # sh library error
    DEVICE_ERROR = 'DEVICE_ERROR'  # v4l2/alsa device error
    THREAD_ERROR = 'THREAD_ERROR'  # fast screenshot thread error


class ControllerState(str, Enum):
    IDLE = 'IDLE'
    STREAM = 'STREAM'
    SCREENSHOT = 'SCREENSHOT'
    FAST_SCREENSHOT = 'FAST_SCREENSHOT'
    RECORDING = 'RECORDING'
    RESET_USB = 'RESET_USB'


class Controller:
    VALID_STATE_TRANSITIONS = [
        (ControllerState.IDLE, ControllerState.STREAM),
        (ControllerState.STREAM, ControllerState.IDLE),
        (ControllerState.IDLE, ControllerState.RESET_USB),
        (ControllerState.RESET_USB, ControllerState.IDLE),
        (ControllerState.IDLE, ControllerState.SCREENSHOT),
        (ControllerState.SCREENSHOT, ControllerState.IDLE),
        (ControllerState.IDLE, ControllerState.FAST_SCREENSHOT),
        (ControllerState.FAST_SCREENSHOT, ControllerState.IDLE),
        (ControllerState.IDLE, ControllerState.RECORDING),
        (ControllerState.RECORDING, ControllerState.IDLE)
    ]

    def __init__(self, janus, gstreamer, ffmpeg, settings):
        self.janus = janus
        self.gstreamer = gstreamer
        self.ffmpeg = ffmpeg
        self.settings = settings

        self._state = ControllerState.IDLE

        self.fast_ss_thread = None

        # recording database
        db_path = f"{settings.recording_files_dir}/db.db"
        engine = create_engine(f"sqlite:///{db_path}")
        if not os.path.exists(db_path):
            Base = declarative_base()
            Base.metadata.create_all(bind=engine, tables=[Recording.__table__])
        Session = sessionmaker(bind=engine)
        self.session = Session()
        self.current_recording = None

    @property
    def state(self):
        """service state"""
        return self._state

    @state.setter
    def state(self, new_state):
        transition = (self._state, new_state)
        if transition in self.VALID_STATE_TRANSITIONS:
            logger.info(f"Controller: {self._state} to {new_state}")
        else:
            logger.warning(f"\nController: {self._state} to {new_state}")
        self._state = new_state

    # Janus
    def start_janus(self, restart=False) -> dict:
        if self.state != ControllerState.IDLE:
            return {
                "success": False,
                "controller_code": ControllerErrorCode.INVALID_STATE.value,
                "controller_state": self.state.value
            }

        result = self.janus.start(restart=restart)
        if (result["success"]):
            self.state = ControllerState.STREAM
        result["controller_state"] = self.state.value
        result["controller_code"] = ControllerErrorCode.SUCCESS.value
        return result

    def stop_janus(self, restart=False) -> dict:
        if self.state != ControllerState.STREAM:
            return {
                "success": False,
                "controller_code": ControllerErrorCode.INVALID_STATE.value,
                "controller_state": self.state.value
            }

        result = self.janus.stop(restart=restart)
        if (result["success"]):
            self.state = ControllerState.IDLE
        result["controller_state"] = self.state.value
        result["controller_code"] = ControllerErrorCode.SUCCESS.value
        return result

    def force_exists_janus(self) -> dict:
        result = force_exists("janus")
        return result

    def force_stop_janus(self) -> dict:
        result = force_stop("janus")
        if result["success"]:
            self.state = ControllerState.IDLE
        return result

    def status_janus(self) -> dict:
        return self.janus.status()

    # Gstreamer
    def start_gstreamer(self, restart=False) -> dict:
        return self.gstreamer.start(restart=restart)

    def stop_gstreamer(self, restart=False) -> dict:
        return self.gstreamer.stop(restart=restart)

    def force_exists_gstreamer(self) -> dict:
        return force_exists("gst-launch-1.0")

    def force_stop_gstreamer(self) -> dict:
        return force_stop("gst-launch-1.0")

    def status_gstreamer(self) -> dict:
        return self.gstreamer.status()

    # Format Video
    def get_format(self):
        """Gets the V4L2 video format. Runs 'v4l2-ctl -V' and 'v4l2-ctl -P'

        Returns:
            dict: V4L2 format
        """
        v4l2_ctl = sh.Command("v4l2-ctl")
        try:
            # resolution status
            cmd = v4l2_ctl("-V")
            display_result = cmd.stdout.decode("utf-8").split("\n")
            status_list = display_result  # add to status

            # framerate status
            cmd = v4l2_ctl("-P")
            framerate_result = cmd.stdout.decode("utf-8").split("\n")
            status_list.extend(framerate_result)  # add to status
        except sh.ErrorReturnCode as err:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.COMMAND_ERROR,
                "error": err.stderr.decode("utf-8")
            }

        status_dict = {}
        for status in status_list[1:]:
            keyval = status.split(":", 1)
            if len(keyval) == 2:
                status_dict[keyval[0].strip()] = keyval[1].strip()

        return {
            "success": True,
            "controller_state": self.state.value,
            "controller_code": ControllerErrorCode.SUCCESS.value,
            "status": status_dict
        }

    def set_format(self,
                   width: int,
                   height: int,
                   pixelformat: str,
                   fps: int) -> dict:
        """Stops janus and sets the V4L2 video format

        Args:
            width (int): video resolution width (example: 1920)
            height (int): video resolution height (example: 1080)
            pixelformat (str): video pixel format (example: MJPG)
            fps (int): framerate (example: 30)

        Returns:
            dict: V4L2 format
        """
        acceptable_states = [ControllerState.IDLE, ControllerState.STREAM]
        # if self.fast_ss_thread is not None:
        if self.state not in acceptable_states:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_STATE
            }

        if self.state == ControllerState.STREAM:
            stop_result = self.stop_janus()
            if not stop_result["success"]:
                stop_result["controller_state"] = self.state.value
                return stop_result

        v4l2_ctl = sh.Command("v4l2-ctl")
        # Change resolution
        try:
            v4l2_ctl("-v",
                     f"width={width},height={height},pixelformat={pixelformat}"
                     )
        except sh.ErrorReturnCode as exc:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.COMMAND_ERROR.value,
                "error": exc.stderr.decode("utf-8")
            }
        logger.success("Changed Resolution")

        status = self.get_format()  # get status
        # prevent crash when switching to 1080p
        if status["status"]["Width/Height"] == "1920/1080":
            reset_result = self.reset_usb()
            if not reset_result["success"]:
                return reset_result

        # Change framerate
        try:
            v4l2_ctl("-p", str(fps))
        except sh.ErrorReturnCode as exc:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.COMMAND_ERROR.value,
                "error": exc.stderr.decode("utf-8")
            }
        logger.success("Changed Framerate")

        status = self.get_format()  # get status

        # self.start_janus(restart=True)  # restart webrtc

        return status

    # Screenshot
    def screenshot(self,
                   process: str,
                   inp_fmt: str,
                   out_fmt: str,
                   width: int,
                   height: int) -> dict:
        """Take a screenshot. WebRTC service must be STOPPED.
           See docs/screenshot.md for full explanation
        Args:
            process (str): cv2 or ffmpeg
            inp_fmt (str): jpg or png
            out_fmt (str): jpg or png
            width (int): resolution width
            height (int): resolution height

        Returns:
            dict: data
        """
        # check valid state
        acceptable_states = [ControllerState.IDLE, ControllerState.STREAM]
        if self.state not in acceptable_states:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_STATE.value
            }

        # check valid process
        valid_processes = ["ffmpeg", "cv2"]
        if process not in valid_processes:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_PROCESS.value
            }

        # Check for valid format
        valid_formats = ["jpg", "png"]
        if inp_fmt not in valid_formats or out_fmt not in valid_formats:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_FORMAT.value
            }

        # stop janus if necessary
        if self.state == ControllerState.STREAM:
            stop_result = self.stop_janus()
            if not stop_result["success"]:
                stop_result["controller_state"] = self.state.value
                return stop_result

        self.state = ControllerState.SCREENSHOT

        filename = f"{self.settings.ss_dir}/ss.{out_fmt}"

        # CV2
        if process == "cv2":
            BARS = 8  # amount of "rainbow bars"
            TOLERANCE = 0.003  # amount of deviation needed

            def get_bar_pixels(frame) -> np.ndarray:
                """gets test pixels from frame

                Args:
                    frame (cv2 image): captured frame

                Returns:
                    np.ndarray: test pixels
                """
                height, width = frame.shape[:-1]
                bar_width = width // BARS
                test_row = height // 2
                pixels = np.zeros((BARS, 3), dtype=int)
                for b in range(BARS):
                    test_col = b * bar_width + bar_width // 2
                    pixels[b] = frame[test_row, test_col]
                return pixels

            # parse parameters
            inp_fmt = "MJPG" if inp_fmt == "jpg" else "YUYV"

            start_time = time.time()  # timestamp

            # cv2 config
            cam = cv2.VideoCapture()
            cam.open(self.settings.v4l2)
            cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*inp_fmt))
            cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            if cam.isOpened():
                iframe = cam.read()[1]  # read first frame
                ref = get_bar_pixels(iframe)  # get first test pixels

                count = 1  # frame counter
                still_looking = True
                while still_looking:
                    count += 1

                    frame = cam.read()[1]  # get next frame

                    test = get_bar_pixels(frame)  # get test pixels

                    # calculate error between new and first test pixels
                    error = ((test / 255 - ref / 255) ** 2).mean()
                    logger.debug(error)

                    if error > TOLERANCE:
                        cv2.imwrite(filename, frame)
                        still_looking = False
                        break

                cam.release()
                dt = time.time() - start_time
                logger.debug(f"Screenshot found in {count} frames, {dt} s")
            else:
                logger.error("Video not opened")
                self.state = ControllerState.IDLE
                return {
                    "success": False,
                    "controler_state": self.state.value,
                    "controller_code": ControllerErrorCode.DEVICE_ERROR.value
                }

        # FFMPEG
        else:
            DELAY = 3

            ffmpeg = sh.Command("ffmpeg")

            # parse parameters
            inp_fmt = "mjpeg" if inp_fmt == "jpg" else "yuyv422"

            try:
                result = ffmpeg(
                    "-hide_banner", "-y",
                    "-f", "v4l2",
                    "-input_format", f"{inp_fmt}",
                    "-video_size", f"{width}x{height}",
                    "-i", self.settings.v4l2,
                    "-ss", f"{DELAY}",
                    "-vframes", "1",
                    filename
                )
            except sh.ErrorReturnCode as exc:
                logger.error(exc)
                self.state = ControllerState.IDLE
                return {
                    "success": False,
                    "controller_state": self.state.value,
                    "controller_code": ControllerErrorCode.COMMAND_ERROR.value,
                    "error": exc.stderr.decode("utf-8")
                }

        logger.success(f"{process}: {inp_fmt} -> {out_fmt} {width}x{height}")

        img = cv2.imread(filename)

        self.state = ControllerState.IDLE
        return {
            "success": True,
            "controller_state": self.state.value,
            "controller_code": ControllerErrorCode.SUCCESS.value,
            "data": cv2.imencode(f".{out_fmt}", img)[1].tobytes()
        }

    def fast_screenshot_mode_start(self,
                                   inp_fmt: str,
                                   out_fmt: str,
                                   width: int,
                                   height: int):
        """Stops Janus. Enters state where screenshots can be retrieved
        quicker than with the normal screenshot call.
        (Janus cannot be used while in this state)

        body:
            inp_fmt (str, optional): input format jpg or png (default: png)
            out_fmt (str, optional): output format jpg or png (default: png)
            width (int, optional): resolution width (default: 1920)
            height (int, optional): resolution height (default: 1080)"""

        # check valid state
        acceptable_states = [ControllerState.IDLE, ControllerState.STREAM]
        if self.state not in acceptable_states:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_STATE.value
            }

        # Check for valid format
        valid_formats = ["jpg", "png"]
        if inp_fmt not in valid_formats or out_fmt not in valid_formats:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_FORMAT.value
            }

        # stop janus if necessary
        if self.state == ControllerState.STREAM:
            stop_result = self.stop_janus()
            if not stop_result["success"]:
                stop_result["controller_state"] = self.state.value
                return stop_result

        self.state = ControllerState.FAST_SCREENSHOT

        self.fast_ss_thread = FastScreenshotReader(inp_fmt, out_fmt,
                                                   width, height)
        self.fast_ss_thread.start()

        return {
            "success": True,
            "controller_state": self.state.value,
            "controler_code": ControllerErrorCode.SUCCESS.value
        }

    def fast_screenshot_mode_stop(self):
        """Exits fast screenshot mode"""

        # check valid state
        acceptable_states = [ControllerState.FAST_SCREENSHOT]

        if self.state not in acceptable_states:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_STATE.value
            }

        result = self.fast_ss_thread.stop()
        if result["success"]:
            self.fast_ss_thread = None
            self.state = ControllerState.IDLE
            result["controller_code"] = ControllerErrorCode.SUCCESS.value
        else:
            result["controller_code"] = ControllerErrorCode.THREAD_ERROR.value
        result["controller_state"] = self.state.value

        return result

    def fast_screenshot(self):
        """Takes a screenshot while in fast screenshot mode.
        Should be quicker than the normal screenshot method"""

        # check valid state
        acceptable_states = [ControllerState.FAST_SCREENSHOT]
        if self.state not in acceptable_states:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_STATE.value
            }

        return self.fast_ss_thread.get_frame()

    def recording_start(self,
                        width: int,
                        height: int,
                        pixelformat: str,
                        fps: int,
                        length: float,
                        name: str = ""):
        """Stops janus and starts a recording
        body:
            width (int): video resolution width (example: 1920)
            height (int): video resolution height (example: 1080)
            pixelformat (str): video pixel format (example: mjpeg or yuyv422)
            fps (int): framerate (example: 30)
            length (int): length (seconds)
        """
        # check valid state
        acceptable_states = [ControllerState.IDLE]
        if self.state not in acceptable_states:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_STATE.value
            }

        # Check for valid format
        valid_formats = ["mjpeg", "yuyv422"]
        if pixelformat not in valid_formats:
            return {
                "success": False,
                "controller_state": self.state.value,
                "controller_code": ControllerErrorCode.INVALID_FORMAT.value
            }

        # stop janus if necessary
        if self.state == ControllerState.STREAM:
            stop_result = self.stop_janus()
            if not stop_result["success"]:
                stop_result["controller_state"] = self.state.value
                return stop_result

        timestamp = datetime.datetime.now().isoformat()

        d = self.settings.recording_files_dir
        filename = f"{d}/Recording_{timestamp}.avi"

        # args_string = " ".join(["-hide_banner", "-y",
        #                         "-f", "v4l2",
        #                         "-input_format", pixelformat,
        #                         "-video_size", f"{width}x{height}",
        #                         "-framerate", str(fps),
        #                         "-thread_queue_size", "1024",
        #                         "-i", self.settings.v4l2,
        #                         "-f", "alsa",
        #                         "-thread_queue_size", "1024",
        #                         "-i", self.settings.alsa,
        #                         "-c:v", "copy",
        #                         "-t", str(length),
        #                         filename
        #                         ])

        args_string = " ".join(["-hide_banner", "-y",
                                "-f", "v4l2",
                                "-input_format", pixelformat,
                                "-video_size", f"{width}x{height}",
                                "-framerate", str(fps),
                                "-thread_queue_size", "1024",
                                "-i", self.settings.v4l2,
                                "-f", "alsa",
                                "-thread_queue_size", "1024",
                                "-i", self.settings.alsa,
                                "-c:v", "h264_v4l2m2m",
                                "-pix_fmt", "yuv420p",
                                "-t", str(length),
                                filename
                                ])

        result = self.ffmpeg.start(arguments=args_string)
        if (result["success"]):
            self.state = ControllerState.RECORDING
            result["filename"] = filename

            # add to database
            if name == "":
                name = None
            self.current_recording = Recording(path=filename,
                                               length=length,
                                               name=name)
            self.session.add(self.current_recording)
            self.session.commit()

        result["controller_state"] = self.state.value
        result["controller_code"] = ControllerErrorCode.SUCCESS.value

        return result

    def recording_stop(self):
        """Stops recording"""
        if self.state != ControllerState.RECORDING:
            return {
                "success": False,
                "controller_code": ControllerErrorCode.INVALID_STATE.value,
                "controller_state": self.state.value
            }

        result = None
        try:
            result = self.ffmpeg.stop()
        except sh.ErrorReturnCode as exc:
            logger.debug(exc.exit_code)

        if (result["success"]):
            self.state = ControllerState.IDLE

            # update database length and size
            path = self.current_recording.path
            self.current_recording.length = video_length(path)
            self.current_recording.size = os.path.getsize(path)
            self.session.commit()

        result["controller_state"] = self.state.value
        result["controller_code"] = ControllerErrorCode.SUCCESS.value
        return result

    def recording_delete(self, filename: str):
        """Deletes a recording

        Args:
            filename (str): filename
        """

        name, ext = os.path.splitext(filename)

        # enforce mp4 or avi
        valid_extensions = [".mp4", ".avi"]
        if ext not in valid_extensions:
            print(ext)
            return {
                "success": False,
                "code": ControllerErrorCode.INVALID_FILENAME.value
            }

        # prevent using different directory
        basename = os.path.basename(name)
        full_path = f"{self.settings.recording_files_dir}/{basename}{ext}"

        # try to delete from database
        condition = Recording.path == full_path
        result = self.session.query(Recording).filter(condition).delete()
        if result == 0:
            logger.warning(f"{full_path} not in database")

        # try to delete file
        if os.path.exists(full_path):
            os.remove(full_path)
            return {
                "success": True,
                "code": ControllerErrorCode.SUCCESS.value
            }
        else:
            return {
                "success": False,
                "code": ControllerErrorCode.INVALID_FILENAME.value
            }

    def recordings_list(self):
        """Returns a list of all recordings stored on the Pi"""

        # files
        files = os.listdir(self.settings.recording_files_dir)

        # database

        # update sizes for those that do not have one
        condition = Recording.size.is_(None)
        for r in self.session.query(Recording).filter(condition):
            r.size = os.path.getsize(r.path)
        self.session.commit()

        data = []
        count = 0
        for r in self.session.query(Recording):
            data.append({
                "id": r.id,
                "path": r.path,
                "length": r.length,
                "size": r.size,
                "timestamp": r.timestamp,
                "name": r.name
            })
            count += 1

        return {
            "success": True,
            "count": count,
            "data": data,
            "files": files
        }

    # USB
    def reset_usb(self):
        """reset usb (ids come from 'lsusb' command)"""

        # check valid state
        acceptable_states = [ControllerState.IDLE]
        if self.state not in acceptable_states:
            return {
                "success": False,
                "controller_state": self.state.value
            }
        self.state = ControllerState.RESET_USB

        DELAY = 2

        # conversions
        id_1 = int(self.settings.id_vendor, 16)
        id_2 = int(self.settings.id_product, 16)

        logger.info("Resetting USB...")
        usb_device = findusb(idVendor=id_1, idProduct=id_2)

        if not usb_device:
            err = f"""Could not find USB device with id_vendor
            {hex(id_1)} and id_product {hex(id_2)}.
            Run 'lsusb' command to list USB devices."""
            logger.error(err)
            self.state = ControllerState.IDLE
            return {
                "success": False,
                "controller_state": self.state.value,
                "error": err
            }

        else:
            usb_device.reset()
            time.sleep(DELAY)  # prevent crash (may remove)
            logger.success("USB has been reset")
            self.state = ControllerState.IDLE
            return {
                "success": True,
                "controller_state": self.state.value
            }

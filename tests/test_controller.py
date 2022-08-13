"""
Tests for Raspberry Pi Hardware Controller
(Required to be run on Raspberry Pi with HDMI-to-USB capture card installeda)
"""

from pydantic import BaseSettings
import pytest
from pi_stream.hardware.background_process import BackgroundProcess
from pi_stream.hardware.controller import Controller


class Settings(BaseSettings):
    """Environment variables for server"""
    port: int = 1234  # Port for this xmlrpc server
    stun_addr: str = "stun.l.google.com:19302"  # STUN server address
    alsa: str = "hw:1"  # ALSA device name
    id_vendor: str = "0x534d"  # First half of 'lsusb' device id (hex)
    id_product: str = "0x2109"  # Second half of 'lsusb' device id (hex)
    ss_dir: str = "/home/pi"  # (development)
    plugins_dir: str = "/home/pi/plugins"  # (development)
    verbose: bool = False


settings = Settings()

janus = BackgroundProcess("janus",
                          f"-P /home/pi/plugins -S {settings.stun_addr}",
                          verbose=settings.verbose)

GSTREAMER_PIPELINE = f"""
    alsasrc device=\"{settings.alsa}\" !
        opusenc bitrate=48000 !
            rtpopuspay ! udpsink host=127.0.0.1 port=5002
    """
gstreamer = BackgroundProcess("gst-launch-1.0",
                              GSTREAMER_PIPELINE,
                              verbose=settings.verbose)


class TestConstructor:
    """Tests for creating a Controller object"""
    def test(self):
        """Create a controller"""
        Controller(janus, gstreamer, settings)


class TestV4l2:
    """Tests for v4l2-ctl operations"""
    def test_get_format(self):
        """Test for 'v4l2-ctl -V' and 'v4l2-ctl -P'"""
        con = Controller(janus, gstreamer, settings)
        assert con.get_format()["success"]

    def test_set_format(self):
        """Test for 'v4l2-ctl -v' and 'v4l2-clt -p'"""
        WIDTH = 1920
        HEIGHT = 1080
        PIXELFORMAT = "MJPG"
        FPS = 30
        con = Controller(janus, gstreamer, settings)
        assert con.set_format(WIDTH, HEIGHT, PIXELFORMAT, FPS)["success"]


class TestScreenshot:
    """Tests for normal screenshot"""
    def test_cv2(self):
        """cv2 screenshot test"""
        INP_FMT = "png"
        OUT_FMT = "png"
        WIDTH = 1920
        HEIGHT = 1080
        con = Controller(janus, gstreamer, settings)
        result = con.screenshot("cv2", INP_FMT, OUT_FMT, WIDTH, HEIGHT)
        # TODO: Assert

    def test_ffmpeg(self):
        """ffmpeg screenshot test"""
        INP_FMT = "png"
        OUT_FMT = "png"
        WIDTH = 1920
        HEIGHT = 1080
        con = Controller(janus, gstreamer, settings)
        result = con.screenshot("ffmpeg", INP_FMT, OUT_FMT, WIDTH, HEIGHT)
        # TODO: Assert


class TestFastScreenshot:
    """Tests for Fast Screenshot Mode"""
    def test_stopped_start(self):
        """Activate Fast Screenshot Mode successfully"""
        INP_FMT = "png"
        OUT_FMT = "png"
        WIDTH = 1920
        HEIGHT = 1080
        con = Controller(janus, gstreamer, settings)
        result = con.fast_screenshot_mode_start(INP_FMT, OUT_FMT,
                                                WIDTH, HEIGHT)

        assert result["success"]

    def test_started_start(self):
        """Try to activate Fast Screenshot Mode when it is already running"""
        INP_FMT = "png"
        OUT_FMT = "png"
        WIDTH = 1920
        HEIGHT = 1080
        con = Controller(janus, gstreamer, settings)
        result = con.fast_screenshot_mode_start(INP_FMT, OUT_FMT,
                                                WIDTH, HEIGHT)
        assert not result["success"]

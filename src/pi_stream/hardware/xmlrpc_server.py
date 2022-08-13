"""XMLRPC server for controlling RPi hardware"""

from xmlrpc.server import SimpleXMLRPCServer

from loguru import logger
from pydantic import BaseSettings

from controller import Controller
from background_process import BackgroundProcess


class Settings(BaseSettings):
    """Environment variables for server"""
    verbose: bool = True

    # xmlrpc
    port: int = 1234

    # STUN
    stun: bool = True  # use STUN (not needed on unrestrictive LAN)
    stun_addr: str = "stun.l.google.com:19302"  # STUN server address

    # Devices
    v4l2: str = "/dev/video0"  # v4l2 device path
    alsa: str = "hw:1"  # ALSA device name
    id_vendor: str = "0x534d"  # First half of 'lsusb' device id (hex)
    id_product: str = "0x2109"  # Second half of 'lsusb' device id (hex)

    # development
    ss_dir: str = "/home/pi"  # (development)
    plugins_dir: str = "/home/pi/plugins"  # (development)

    # must match docker compose
    recording_files_dir: str = "/home/pi/recordings"


if __name__ == "__main__":
    settings = Settings()

    # gstreamer settings
    GSTREAMER_PIPELINE = f"""
    alsasrc device=\"{settings.alsa}\" !
        opusenc bitrate=48000 !
            rtpopuspay ! udpsink host=127.0.0.1 port=5002
    """

    # Create server
    addr = ('localhost', settings.port)
    with SimpleXMLRPCServer(addr, allow_none=True) as server:
        server.register_introspection_functions()

        # create janus process wrapper
        janus_args = ""
        if settings.stun:
            janus_args = f"-P {settings.plugins_dir} -S {settings.stun_addr}"
        else:
            janus_args = f"-P {settings.plugins_dir}"

        janus = BackgroundProcess("janus",
                                  janus_args,
                                  verbose=settings.verbose)

        # create gstreamer process wrapper
        gstreamer = BackgroundProcess("gst-launch-1.0",
                                      GSTREAMER_PIPELINE,
                                      verbose=settings.verbose)

        # create ffmpeg process wrapper (args provided at start-time)
        ffmpeg = BackgroundProcess("ffmpeg",
                                   verbose=settings.verbose)

        controller = Controller(janus, gstreamer, ffmpeg, settings)
        server.register_instance(controller)

        # Run the server's main loop
        if settings.verbose:
            if settings.stun:
                logger.debug(f"Using STUN: {settings.stun_addr}")
            else:
                logger.debug(f"Using LAN (No STUN)")
            logger.debug(f"Using ALSA device: {settings.alsa}")
            logger.debug(f"Using v4l2 device: {settings.v4l2}")

            idv = settings.id_vendor
            idp = settings.id_product
            logger.debug(f"USB id_vendor:{idv},id_product:{idp}")

        logger.info(f"Server Started at {addr}")
        server.serve_forever()

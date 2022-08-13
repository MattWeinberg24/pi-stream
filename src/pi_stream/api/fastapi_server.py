"""FastAPI Server for WebRTC Stream"""

import io
import os
import time
import xmlrpc.client

from pydantic import BaseModel, BaseSettings
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import uvicorn


class Settings(BaseSettings):
    """Environment Variables"""
    host: str = "0.0.0.0"
    port: int = 8000
    xmlrpc_addr: str = "http://localhost:1234"
    static_files_dir: str = "/home/pi/www"
    recording_files_dir: str = "/home/pi/recordings"
    verbose: bool = False


class VideoFormat(BaseModel):
    """v4l2-ctl video format"""
    width: int
    height: int
    pixelformat: str
    fps: int


class RecordingFormat(BaseModel):
    width: int
    height: int
    pixelformat: str
    fps: int
    length: int


class FastScreenshotFormat(BaseModel):
    """fast screenshot format"""
    inp_fmt: str = "png"  # "jpg" OR "png"
    out_fmt: str = "png"  # "jpg" OR "png"
    width: int = 1920
    height: int = 1080


# Create objects and connect to xmlrpc server
settings = Settings()
xc = xmlrpc.client.ServerProxy(settings.xmlrpc_addr,
                               use_builtin_types=True,
                               allow_none=True)
app = FastAPI()


@app.on_event("startup")
async def startup():
    """FastAPI startup"""
    logger.success("Starting API")
    if settings.verbose:
        logger.debug("Using verbose mode")

# Static Files
try:
    # HTML/Javascript Frontend
    app.mount("/static",
              StaticFiles(directory=settings.static_files_dir),
              name="static")
    # Recordings
    app.mount("/recordings",
              StaticFiles(directory=settings.recording_files_dir),
              name="recordings")
except RuntimeError as e:
    logger.error(e)


@app.post("/")
async def read_root():
    """Test Route"""
    return {"Hello": "World"}


@app.post("/janus/start")
async def start_janus():
    """Starts the Janus WebRTC server\n
    If returns success but behavior is not as expected:\n
    1. Check that STUN server config/connection is correct\n
    2. Call force_stop_webrtc and try again\n
    3. Call reset_usb and try again"""
    return xc.start_janus()


@app.post("/janus/stop")
async def stop_janus():
    """Stops a Janus WebRTC server that was started with /janus/start\n
    If returns success but behavior is not as expected:\n
    1. Force-stop WebRTC (using the appropriate API call) instead"""
    return xc.stop_janus()


@app.post("/janus/force_stop")
async def force_stop_janus():
    """Runs pkill with SIGINT on any Janus process on the machine"""
    return xc.force_stop_janus()


@app.post("/janus/force_exists")
async def force_exists_webrtc():
    """Runs pgrep, looking for any Janus process on the device"""
    return xc.force_exists_janus()


@app.post("/audio/start")
async def start_audio():
    """Starts the gstreamer pipeline, allowing for audio to be captured\n
    For audio to be sent, requires the Janus WebRTC server to be running\n
    If returns success but behavior is not as expected:\n
    1. Check that ALSA config is correct\n
    2. Call force_stop_audio and try again\n
    3. Call reset_usb and try again"""
    return xc.start_gstreamer()


@app.post("/audio/stop")
async def stop_audio():
    """Stops a gstreamer pipeline that was started /audio/start\n
    If returns success but behavior is not as expected:\n
    1. Force-stop audio (using the appropriate API call) instead"""
    return xc.stop_gstreamer()


@app.post("/audio/force_stop")
async def force_stop_audio():
    """Runs pkill with SIGINT on any gstreamer process on the device"""
    return xc.force_stop_gstreamer()


@app.post("/audio/force_exists")
async def force_exists_audio():
    """Runs pgrep, looking for any Janus process on the device"""
    return xc.force_exists_gstreamer()


@app.post("/set_format")
async def set_format(vfmt: VideoFormat):
    """Stops janus and sets the V4L2 video format\n
    body:\n
        width (int): video resolution width (example: 1920)\n
        height (int): video resolution height (example: 1080)\n
        pixelformat (str): video pixel format (example: MJPG)\n
        fps (int): framerate (example: 30)\n
    If returns success but behavior is not as expected:\n
    1. Check that STUN server config/connection is correct\n
    2. Call force_stop_webrtc and try again\n
    3. Call reset_usb and try again"""
    return xc.set_format(vfmt.width, vfmt.height, vfmt.pixelformat, vfmt.fps)


@app.post("/get_format")
async def get_format():
    """Gets the v4l2 format using v4l2-ctl"""
    return xc.get_format()


@app.get("/screenshot")
async def screenshot(tasks: BackgroundTasks,
                     process: str = "cv2",
                     inp_fmt: str = "png", out_fmt: str = "png",
                     width: int = 1920, height: int = 1080):
    """Stops WebRTC service (if it is on), takes and returns a screenshot,
    resets the USB, then restarts WebRTC service\n
    params:\n
        process (str, optional): ffmpeg OR cv2 (default: cv2)\n
        inp_fmt (str, optional): input format jpg or png (default: png)\n
        out_fmt (str, optional): output format jpg or png (default: png)\n
        width (int, optional): resolution width (default: 1920)\n
        height (int, optional): resolution height (default: 1080)"""

    # stop janus if it is running
    # xc.stop_janus()

    # attempt to take the screenshot
    result = xc.screenshot(process, inp_fmt, out_fmt, width, height)

    # return immediately if not successful
    if not result["success"]:
        return result

    # reset USB in the background
    # Note: resolution reverts to 1920x1080
    # tasks.add_task(reset_usb_and_start_janus)
    tasks.add_task(xc.reset_usb)  # Note: resolution reverts to 1920x1080

    # prepare response
    mime_type = "image/{}".format({"jpg": "jpeg", "png": "png"}[out_fmt])
    content = io.BytyesIO(result["data"])
    response = StreamingResponse(content, media_type=mime_type)
    response.headers["Content-Disposition"] = f"inline; filename=ss.{out_fmt}"

    return response


@app.post("/fast_screenshot/start")
async def fast_screenshot_mode_start(sfmt: FastScreenshotFormat):
    """Stops Janus. Enters state where screenshots can be retrieved quicker
    than with the normal screenshot call.\n
    (Janus cannot be used while in this state)\n
    body:\n
        inp_fmt (str, optional): input format jpg or png (default: png)\n
        out_fmt (str, optional): output format jpg or png (default: png)\n
        width (int, optional): resolution width (default: 1920)\n
        height (int, optional): resolution height (default: 1080)"""
    return xc.fast_screenshot_mode_start(sfmt.inp_fmt,
                                         sfmt.out_fmt,
                                         sfmt.width,
                                         sfmt.height)


@app.post("/fast_screenshot/stop")
async def fast_screenshot_mode_stop(tasks: BackgroundTasks):
    """Exits fast screenshot mode"""
    result = xc.fast_screenshot_mode_stop()

    # reset USB in the background
    tasks.add_task(xc.reset_usb)  # Note: resolution reverts to 1920x1080

    return result


@app.get("/fast_screenshot")
async def fast_screenshot():
    """Takes a screenshot while in fast screenshot mode.\n
    Should be quicker than the normal screenshot method"""
    result = xc.fast_screenshot()

    if result["success"]:
        out_fmt = result["format"]

        mime_type = "image/{}".format({"jpg": "jpeg", "png": "png"}[out_fmt])
        content = io.BytesIO(result["data"])
        response = StreamingResponse(content, media_type=mime_type)
        disposition = f"inline; filename=ss.{out_fmt}"
        response.headers["Content-Disposition"] = disposition

        if result:
            return response

    return result


@app.post("/recording/start")
async def recording_start(rfmt: RecordingFormat):
    """Stops janus and starts a recording\n
    body:\n
        width (int): video resolution width (example: 1920)\n
        height (int): video resolution height (example: 1080)\n
        pixelformat (str): video pixel format (example: MJPG)\n
        fps (int): framerate (example: 30)\n
        length (int): length of the recording (seconds)\n
    If returns success but behavior is not as expected:\n
    1. Call reset_usb and try again"""
    logger.info(rfmt)
    return xc.recording_start(rfmt.width,
                              rfmt.height,
                              rfmt.pixelformat,
                              rfmt.fps,
                              rfmt.length)


@app.post("/recording/stop")
async def recording_stop():
    """Stops recording early"""
    return xc.recording_stop()


@app.post("/recording/delete/{filename}")
async def recording_delete(filename: str):
    """Deletes a recording

    Args:
        filename (str): filename
    """
    return xc.recording_delete(filename)


@app.post("/recording/list")
async def recordings_list(request: Request):
    """Returns a list of all recordings stored on the Pi"""
    recordings = xc.recordings_list()

    # add urls
    url = request.base_url
    for d in recordings["data"]:
        basename = os.path.basename(d["path"])
        d["url"] = f"{url}recordings/{basename}"

    return recordings


@app.post("/status")
async def status_webrtc():
    """Gets status of WebRTC (Janus) and audio (gstreamer) processes"""
    return {
        "janus": xc.status_janus(),
        "gstreamer": xc.status_gstreamer()
    }


@app.post("/reset_usb")
async def reset_usb():
    """Resets the USB device corresponding with the capture card\n
    Useful for troubleshooting"""
    return xc.reset_usb()


def reset_usb_and_start_janus():
    """resets USB then starts webrtc (janus)"""
    xc.reset_usb()
    xc.start_janus()


if __name__ == "__main__":

    # connect to XMLRPC server...
    addr = settings.xmlrpc_addr
    while True:
        try:
            logger.info(xc.system.listMethods())
            logger.success(f"xmlrpc: connected to {addr}")
            break
        except ConnectionRefusedError:
            logger.error(f"xmlrpc: not connected to {addr}. Trying again...")
            time.sleep(1)

    log_level = "info"
    if settings.verbose:
        log_level = "debug"

    uvicorn.run("fastapi_server:app",
                host=settings.host,
                port=settings.port,
                log_level=log_level)

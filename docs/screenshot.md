# pi-stream Screenshot Overview

Screenshots are an extra feature of this API disconnected from the core webrtc connection. There are currently two methods of taking a screenshot:
1. /screenshot
2. /fast_screenshot

## /screenshot
### GET /screenshot
```
Stops WebRTC service (if it is on), takes and returns a screenshot,
resets the USB, then restarts WebRTC service
params:
    process (str, optional): ffmpeg OR cv2 (default: cv2)
    inp_fmt (str, optional): input format jpg or png (default: png)
    out_fmt (str, optional): output format jpg or png (default: png)
    width (int, optional): resolution width (default: 1920)
    height (int, optional): resolution height (default: 1080)
```        
This endpoint will stop the Janus server and begin a seperate ffmpeg or opencv process for taking a single screenshot. For `inp_fmt`, jpg corresponds to MJPG video capture and png corresponds to YUYV video capture (this is most likely going to change). In the current development state Janus does not automatically restart after taking a screenshot, however that is the ideal implementation here.

## /fast_screenshot
### POST /fast_screenshot/start
```
Stops Janus. Enters state where screenshots can be retrieved quicker
than with the normal screenshot call.
(Janus cannot be used while in this state)
body:
    inp_fmt (str, optional): input format jpg or png (default: png)
    out_fmt (str, optional): output format jpg or png (default: png)
    width (int, optional): resolution width (default: 1920)
    height (int, optional): resolution height (default: 1080)
```
This endpoint will stop the Janus server and begin a seperate ffmpeg or opencv process (more specifically, a seperate non-blocking python thread) for taking multiple consecutive screenshots. For `inp_fmt`, jpg corresponds to MJPG video capture and png corresponds to YUYV video capture (this is most likely going to change). The difference here is that this "mode" will continue to read screenshot-able frames until it is turned off. This removes the startup delay for consecutive screenshots, hence the "fast". The disadvantage here is that the mode needs to be explicitly shut off, and the format cannot be changed while the mode is still active. The current implementation only supports opencv.
### GET /fast_screenshot
```
Takes a screenshot while in fast screenshot mode.
Should be quicker than the normal screenshot method
```
This endpoint loads a frame captured while fast screenshot mode is active
### POST /fast_screenshot/stop
```
Exits fast screenshot mode
```
This endpoint brings the service back to an idle state where janus can then be restarted

## OpenCV vs FFMPEG
These two processes differ in how they handle capture card startup delay, as well as very slight differences in image content.
### OpenCV
In the project's current state this is the more reliable method, as it uses an automated algorithm for detecting when proper frames are being captured. Put simply, a test frame that looks like vertical bars of different colors may appear when the device begins capture. Using OpenCV, the point where this ends is able to be detected.
### FFMPEG
This was the first method of taking screenshots implemented. The downside is that there is a set three second delay before capture to account for the startup. It is left in mostly for test purposes.

## Why?

### Why can't a screenshot be taken while the Janus stream is running?
While a screenshot can be taken using external tools on the client side, to get a screenshot directly from the video device on the server, whichever process is taking the screenshot generally needs to have sole "access" to that device. The process consuming the video for Janus is the Janus plugin provided by [catid/kvm](https://github.com/catid/kvm), which does not have native support for screenshots.

### Could the plugin be modified to support simultaneous screenshots?
Yes. Modifying that plugin is something I hope to look into in the future, which would involve learning the Janus plugin API as well as more about system-level C/C++ coding. The initial commit of this repository is based off a summer internship project I had, and due to the time constraint this solution was deemed sufficient. The only downside to this approach is that the format of the screenshot would most likely have to match the format of the current stream, which means raw format screenshots could not be taken this way as the plugin only adequately works with MJPG.

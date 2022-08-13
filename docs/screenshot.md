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
This endpoint will stop the Janus server and begin a seperate ffmpeg or opencv process for taking a single screenshot. For `inp_fmt`, jpg corresponds to MJPG video capture and png corresponds to YUYV video capture (this is most likely going to change). In the current development state Janus does not automatically restart after taking a screenshot, however that is the ideal implementation here. There are small differences in the image itself depending on whether ffmpeg or opencv is used, however they are negligible in most use cases.

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
This endpoint will stop the Janus server and begin a seperate ffmpeg or opencv process for taking multiple consecutive screenshots. For `inp_fmt`, jpg corresponds to MJPG video capture and png corresponds to YUYV video capture (this is most likely going to change). The difference here is that this "mode" will continue to read screenshot-able frames until it is turned off. This removes the startup delay for consecutive screenshots, hence the "fast". The disadvantage here is that the mode needs to be explicitly shut off. The current implementation only supports opencv.

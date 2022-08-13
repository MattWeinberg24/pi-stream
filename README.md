# pi-stream
Raspberry Pi/FastAPI service for streaming HDMI video/audio over the internet using the WebRTC protocol

Utilizes https://github.com/meetecho/janus-gateway, https://github.com/catid/kvm

## Requirements
1. Raspberry Pi 4 running 32-bit Raspberry Pi OS (tested with 4 GB RAM)
    * Username "pi" preferred
    * Docker must be installed (https://docs.docker.com/engine/install/debian/)
    * The pi must have a way to connect to the outer internet (needed for docker build)
2. HDMI-to-USB Capture Card supporting MJPG capture format
3. (If on corporate network) A STUN/TURN server (see [docs/stun.md](docs/stun.md))

## Setup
1. 
```bash
cd /home/pi
git clone https://github.com/MattWeinberg24/pi-stream.git
cd pi-stream
```
2. edit `docker-compose.yml` in vim or nano to configure environment variables

## Usage
1. `docker compose up`
2. Navigate to http://\<PI IP\>:\<FASTAPI PORT\>/static/index.html in Chrome or Edge (Firefox untested)
3. Enter STUN/TURN information for frontend
4. Use the API
    * Test buttons available on the above site
    * Full API documentation available at http://\<PI IP\>:\<FASTAPI PORT\>/docs

* Frontend debug messages can be found in the browser console
* Backend debug messages can be found through docker's output

### Ports
* 8088
  * Janus Gateway WebRTC Server
* 8000
  * Python FastAPI
  * HTML/Javascript served at /static/index.html on this port
  * Docs served at /docs on this port
* 5002
  * gstreamer opus RTP audio stream
  * (Used internally)

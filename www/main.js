let server = null;
if(window.location.protocol === 'http:') {
    server = "http://" + window.location.hostname + ":8088/janus";
} else {
    server = "https://" + window.location.hostname + ":8089/janus";
}

let janus = null;

//video
let handle = null;
let opaqueId = "oid-"+Janus.randomString(12);
let videoBitrateTimer = null;

//audio
let handle2 = null;
let opaqueId2 = "streamingtest-"+Janus.randomString(12);
let streamsList = {};
let selectedStream = 1;
let audioBitrateTimer = null;

//recording
let recorderStream = new MediaStream();

function getAudioStreamInfo() {
	// Send a request for more info on the mountpoint we subscribed to
	let body = { request: "info", id: parseInt(selectedStream) || selectedStream };
	handle2.send({ message: body, success: function(result) {
		if(result && result.info) {
			// $('#metadata').html(escapeXmlTags(result.info.metadata));
			console.log(result.info);
		}
	}});
}

function sendData(text) {
    handle.data({
        text: text
    });
}

function stopVideoBitrateTimer() {
    if (videoBitrateTimer) {
        clearInterval(videoBitrateTimer);
    }
    videoBitrateTimer = null;
}

let videoWidth = 0, videoHeight = 0;

function startVideoBitrateTimer() {
    stopVideoBitrateTimer();
    videoBitrateTimer = setInterval(function() {
        let videoBitrate = handle.getBitrate();
        document.getElementById("video-bitrate-text").textContent = videoBitrate;
        let video = document.getElementById("remotevideo");
        videoWidth = video.videoWidth;
        videoHeight = video.videoHeight;
        document.getElementById("resolution-text").textContent = videoWidth + "x" + videoHeight;
    }, 1000);
}

function stopAudioBitrateTimer() {
    if (audioBitrateTimer) {
        clearInterval(audioBitrateTimer);
    }
    audioBitrateTimer = null;
}

function startAudioBitrateTimer() {
    stopAudioBitrateTimer();
    audioBitrateTimer = setInterval(function() {
        let audioBitrate = handle2.getBitrate();
        console.log(audioBitrate);
        document.getElementById("audio-bitrate-text").textContent = audioBitrate;
    }, 1000);
}

function watchVideoStream() {
    console.log("watchVideoStream");
    let body = { "request": "watch" };
    handle.send({"message": body});
}

function startVideoStream(jsep) {
    console.log("startVideoStream");
    let body = { request: "start" };
    handle.send({ message: body, jsep: jsep });
}

function stopVideoStream() {
    stopVideoBitrateTimer();
    stopCapture();
    console.log("stopVideoStream");
    let body = { request: "stop" };
    handle.send({ message: body });
    handle.hangup();
}

function startAudioStream() {
    Janus.log("Getting Audio Streams List");
    let body = { request: "list" };
    Janus.log("Sending message:", body);
    handle2.send({ message: body, success: function(result) {
		if(!result) {
			Janus.warn("Got no response to our query for available streams");
			return;
		}
		if(result["list"]) {
			let list = result["list"];
			Janus.log("Got a list of available streams:", list);
			let streamsList = {};
			for(let mp in list) {
				streamsList[list[mp]["id"]] = list[mp];
			}
            body = { request: "watch", id: parseInt(selectedStream) || selectedStream };
            handle2.send({message: body});

            getAudioStreamInfo();
		}
	}});
}

function attachAudioStream() {
    // Attach to Streaming plugin
    janus.attach({
        plugin: "janus.plugin.streaming",
        opaqueId: "streaming-"+Janus.randomString(12),
        success: function(pluginHandle) {
            handle2 = pluginHandle;
            Janus.log("Plugin attached! (" + handle2.getPlugin() + ", id=" + handle2.getId() + ")");
            startAudioStream();
        },
        error: function(error) {
            Janus.error("  -- Error attaching plugin... ", error);
        },
        iceState: function(state) {
            Janus.log("Audio ICE state changed to " + state);
        },
        webrtcState: function(on) {
            Janus.log("Audio WebRTC PeerConnection is " + (on ? "up" : "down") + " now");
        },
        slowLink: function(uplink, lost, mid) {
            Janus.warn("Problems " + (uplink ? "sending" : "receiving") +
                " audio packets on mid " + mid + " (" + lost + " lost packets)");
        },
        onmessage: function(msg, jsep) {
            Janus.log(" ::: Got an audio message :::", msg);
            let result = msg["result"];
            let audioText = document.getElementById("audio-text");
            if(result) {
                if(result["status"]) {
                    let status = result["status"];
                    if(status === 'starting')
                        audioText.textContent = 'starting';
                    else if(status === 'started')
                        audioText.textContent = 'attached';
                    else if(status === 'stopped')
                        stopAudioStream();
                } 
            } else if(msg["error"]) {
                Janus.error(msg["error"]);
                stopStream();
                return;
            }
            if(jsep) {
                Janus.log("Handling audio SDP as well...", jsep);
                let stereo = (jsep.sdp.indexOf("stereo=1") !== -1);
                // Offer from the plugin, let's answer
                handle2.createAnswer(
                    {
                        jsep: jsep,
                        // We want recvonly audio/video and, if negotiated, datachannels
                        media: { audioSend: false, videoSend: false, data: true },
                        customizeSdp: function(jsep) {
                            jsep.sdp = jsep.sdp.replace("useinbandfec=1", "useinbandfec=1;maxaveragevideoBitrate=96000");
                            if(stereo && jsep.sdp.indexOf("stereo=1") == -1) {
                                // Make sure that our offer contains stereo too
                                Janus.log("Replacing Stereo");
                                jsep.sdp = jsep.sdp.replace("useinbandfec=1", "useinbandfec=1;stereo=1;maxaveragevideoBitrate=1000");
                            }
                        },
                        success: function(jsep) {
                            Janus.log("Got SDP!", jsep);
                            let body = { request: "start" };
                            handle2.send({ message: body, jsep: jsep });
                        },
                        error: function(error) {
                            Janus.error("WebRTC error:", error);
                            Janus.error("WebRTC error... " + error.message);
                        }
                    });
            }
        },
        onremotetrack: function(track, mid, on) {
            Janus.log("Remote track (mid=" + mid + ") " + (on ? "added" : "removed") + ":", track);

            // If we're here, a new track was added
            let stream = null;
            if(track.kind === "audio") {
                // New audio track: create a stream out of it, and use a hidden <audio> element
                stream = new MediaStream();
                stream.addTrack(track);
                Janus.log("Created remote audio stream:", stream);
                let remoteaudio = document.getElementById("remoteaudio");
                Janus.attachMediaStream(remoteaudio, stream);
                // startAudioBitrateTimer(); // Bitrate only for video?
            } 
        },
        oncleanup: function() {
            Janus.log(" ::: Got an audio cleanup notification :::");
            stopAudioBitrateTimer();
        }
    });
}

function attachVideoStream() {
    //Attach to kvm plugin
    janus.attach({
        plugin: "kvm",
        opaqueId: opaqueId,
        success: function(pluginHandle) {
            handle = pluginHandle;
            Janus.log("Plugin attached! (" + handle.getPlugin() + ", id=" + handle.getId() + ")");
            watchVideoStream();
        },
        error: function(error) {
            Janus.error("  -- Error attaching plugin... ", error);
        },
        iceState: function(state) {
            Janus.log("Video ICE state changed to " + state);
        },
        webrtcState: function(on) {
            Janus.log("Video WebRTC PeerConnection is " + (on ? "up" : "down") + " now");
        },
        onmessage: function(msg, jsep) {
            Janus.log(" ::: Got a video message :::", msg);
            let result = msg["result"];
            let statustext = document.getElementById("status-text");
            if (result) {
                if (result["status"]) {
                    let status = result["status"];
                    if(status === 'starting') {
                        statustext.textContent = "starting";
                    }
                    else if(status === 'started') {
                        statustext.textContent = "started";
                    }
                    else if(status === 'stopped') {
                        statustext.textContent = "stopped";
                    }
                }
            } else if (msg["error"]) {
                console.error(msg["error"]);
                stopVideoStream();
                watchVideoStream();
                return;
            }

            if(jsep) {
                Janus.log("Handling video SDP as well...", jsep);
                // Offer from the plugin, let's answer
                handle.createAnswer({
                    jsep: jsep,
                    // We want recvonly audio/video and, if negotiated, datachannels
                    media: { audioSend: false, videoSend: false, data: true },
                    customizeSdp: function(jsep) {
                        // Modify jsep.sdp here
                    },
                    success: function(jsep) {
                        Janus.log("Got Video SDP!", jsep);
                        startVideoStream(jsep);
                    },
                    error: function(error) {
                        Janus.error("Video WebRTC error:", error);
                    }
                });
            }
        },
        onremotetrack: function(stream, mid, on) {
            Janus.log(" ::: Got a remote video stream :::", stream);
            let remotevideo = document.getElementById("remotevideo");
            try {
                Janus.attachMediaStream(remotevideo, stream);
                recorderStream.addTrack(stream)
                startVideoBitrateTimer();
            }
            catch(e) {
                console.log(`Error in attaching remote video stream: ${e}`);
            }
        },
        slowLink: function(uplink, lost, mid) {
            Janus.warn("Problems " + (uplink ? "sending" : "receiving") +
                " video packets on mid " + mid + " (" + lost + " lost packets)");
        },
        oncleanup: function() {
            Janus.log(" ::: Got a video cleanup notification :::");
            stopVideoBitrateTimer();
        }
    });
}

function stopAudioStream() {
    stopAudioBitrateTimer();
	let body = { request: "stop" };
	handle2.send({ message: body });
	handle2.hangup();
}

function recordingSetup() {

    let record = document.getElementById("record-btn");
    let stop = document.getElementById("stop-btn");    
    let clips = document.getElementById("clips");
      
    let chunks = [];

    const mediaRecorder = new MediaRecorder(recorderStream);

    //record button
    record.addEventListener("click", function() {
        mediaRecorder.start();
        console.log(mediaRecorder.state);
        console.log("recorder started");
        record.style.background = "red";
        record.style.color = "black";
    })

    //stop button
    stop.addEventListener("click", function() {
        mediaRecorder.stop();
        console.log(mediaRecorder.state);
        console.log("recorder stopped");
        record.style.background = "";
        record.style.color = "";
    });

    //when the recording stops...
    mediaRecorder.onstop = function(e) {
        console.log("Stopped Media Recorder");
        let name = prompt("Clip filename:")

        const blob = new Blob(chunks, { 'type' : 'video/mp4' });
        chunks = [];
        const videoURL = URL.createObjectURL(blob);
        console.log(videoURL);

        let link = document.createElement('a');
        link.download = name;
        link.textContent = name;
        link.href = videoURL;
        clips.appendChild(link)
        console.log("recorder stopped");
    }

    //add data to recording when data is available
    mediaRecorder.ondataavailable = function(e) {
        chunks.push(e.data);
    }     
}

document.addEventListener("DOMContentLoaded", function() {

    //try to get url params for STUN
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    document.getElementById("stun").value = urlParams.get("ice");
    document.getElementById("stun-uname").value = urlParams.get("u");
    document.getElementById("stun-pword").value = urlParams.get("p");


    document.getElementById("start").addEventListener("click", e => {

        // let pre_options = document.getElementById("pre-options-container");
        // pre_options.style.display = "none";
        // let post_options = document.getElementById("post-options-container");
        // post_options.style.display = "flex"   

        //destroy janus if it already exists
        if (janus != null) {
            janus.destroy();
            janus = null;
        }

        recordingSetup()

        //parse stun server
        let iceServerIP = document.getElementById("stun").value;
        let turnUname = document.getElementById("stun-uname").value;
        let turnPword = document.getElementById("stun-pword").value;
        let iceServer = iceServerIP ? [{
            urls: iceServerIP,
            username: turnUname,
            credential: turnPword
        }] : [];
        console.log("Using ICE server: " + iceServerIP);

        // Initialize the library (all console debuggers enabled)
        Janus.init({
            debug: "all",
            callback: function() {
                if(!Janus.isWebrtcSupported()) {
                    console.error("No WebRTC support");
                    return;
                }

                //audio
                janus = new Janus({
                    longPollTimeout: 0,
                    server: server,
                    iceServers: iceServer,
                    success: function() {
                        attachAudioStream();
                        attachVideoStream();
                    },
                    error: function(error) {
                        Janus.error(error);
                    }
                });
                
        }});
    });    
});


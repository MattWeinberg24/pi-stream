# STUN/TURN Server Config

*For reference on what this means, read https://webrtcforthecurious.com/docs/03-connecting*

If the Pi and Client are not on the same LAN, then a STUN/TURN server is needed to initiate the WebRTC connection.

On unrestrictive networks you should be able to use a public STUN server such as Google's (stun.l.google.com:19302), which this repository uses by default. However, for use on networks such as private corporate networks, you will need to create your own STUN/TURN server within that corporate network.

A simple coturn (https://github.com/coturn/coturn) server running on some reachable Linux device can suffice.

For minimum functionality, make sure the following is in `/etc/turnserver.conf`:
```
verbose
fingerprint
log-file=/var/log/turnserver/turnserver.log 
syslog
simple-log
```

However for production use, it is wise to look into all of coturn's configuration options.
# Janus Config

The config files themselves contain extensive documentation/templates. Rebuild using the instructions in the docker folder after editing any of these files. The following properties should be specifically of note:

## janus.jcfg
```
debug_level
slowlink_threshhold
nice_debug
ignore_mdns
```

## janus.plugin.streaming.jcfg
Stream input config can be changed in the `rtp-sample` section

## janus.transport.http.jcfg
```
admin_http
admin_port
```
# To build
`cd docker`

## Base
Only if base is not up to date...
```bash
# if cross-architecture
docker buildx rm pi_stream_base_builder || true 
docker buildx create --name pi_stream_base_builder --use
docker buildx build --load --platform linux/arm/v7 -t="pi-stream-base:snapshot" -f Base_Dockerfile ..

#if on pi
docker build -t="pi-stream-api:snapshot" -f Base_Dockerfile ..
```

## API and Hardware (if on pi)
```bash
docker compose build
```

## API
```bash
# if cross-architecture
docker buildx rm pi_stream_api_builder || true 
docker buildx create --name pi_stream_api_builder --use
docker buildx build --load --platform linux/arm/v7 -t="pi-stream-api:snapshot" -f API_Dockerfile ..

#if on pi
docker build -t="pi-stream-api:snapshot" -f API_Dockerfile ..
```

## Hardware
Useful if changing Janus config
```bash
# if cross-architecture
docker buildx rm pi_stream_hardware_builder || true 
docker buildx create --name pi_stream_hardware_builder --use
docker buildx build --load --platform linux/arm/v7 -t="pi-stream-hardware:snapshot" -f Hardware_Dockerfile ..

#if on pi
docker build -t="pi-stream-hardware:snapshot" -f Hardware_Dockerfile ..
```
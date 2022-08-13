from usb.core import find as finddev

# replace args with output from 'lsusb'
dev = finddev(idVendor=0x534d, idProduct=0x2109)

dev.reset()

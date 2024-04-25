# bsa_kits
Kits for BSA Troop 701

# installation

## install micropython

``` Shell
# erase flash
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash

# install micropython
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460000 write_flash -z 0x1000 ./ESP32_GENERIC-20240222-v1.22.2.bin
```

## install ampy

``` Shell
pip install adafruit-ampy
```

## install scripts

``` Shell
# install remote controller
ampy --port /dev/ttyUSB0 put controller/mp_button.py
ampy --port /dev/ttyUSB0 put controller/boot.py

# install remote controller
ampy --port /dev/ttyUSB0 put rank6/boot.py

# install remote controller
ampy --port /dev/ttyUSB0 put stage4/boot.py
```

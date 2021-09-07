#! /usr/bin/env python3

"""Simple example using the Joy-IT Explorer 700 and the Pi3g BME688
breakout board.  The bme68x library has to be installed, you can use
`pip3 install bme68x`.

Links:
 * https://github.com/pi3g/bme68x-python-library
 * https://joy-it.net/en/products/RB-Explorer700

"""

import time
import threading
import json
import smbus
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import bme68x
import spidev as SPI
import SSD1306

## I²C address of the BME688 sensor.
BME_I2C_ADDR = 0x77

## I²C address of the IO expander.
PCF_8574_ADDR = 0x20

# Raspberry Pi pin configuration:
RST = 19
DC = 16
bus = 0
device = 0

# File name for the data store.
DATASTOREFNAME = "DATASTORE.$"

# Global data array.
dataarr = []

# Global variable indicating that we are still running.
RUNNING = True

def loop_new_env_data(bme):
    """Loop that gets every 30s new environmental data.

    Usually this function runs in a separated thread and does not return.

    @param bme: BME68X object to acces the sensor
    """
    global dataarr
    bus = smbus.SMBus(1)
    while RUNNING:
        # Get newest data.
        data = bme.get_data()
        # Only keep the last 100000 values.
        narr = dataarr[-100000:]
        # Append to our data array.
        narr.append(data)
        # And now overwrite with the new array.
        dataarr = narr
        print(data)
        # Now flash the LED.
        pcf = bus.read_byte(PCF_8574_ADDR)
        bus.write_byte(PCF_8574_ADDR, pcf ^ 0x10)
        time.sleep(30)


def init_display():
    """Initialise display and get object.

    @return: display object.
    """
    # 128x32 display with hardware I2C:
    disp = SSD1306.SSD1306(rst=RST, dc=DC, spi=SPI.SpiDev(bus, device))
    # Initialize library.
    disp.begin()
    # Clear display.
    disp.clear()
    disp.display()
    return disp


def display_data(data, draw):
    """Display the BME688 data on the draw object.

    @param data: dictionary with measurement
    @param draw: draw object
    """
    draw.text((1, 10), "T = %f" % data["temperature"], fill="white")
    draw.text((1, 20), "p = %f" % data["pressure"], fill="white")
    draw.text((1, 30), "H = %f" % data["humidity"], fill="white")
    draw.text((1, 40), "R = %f" % data["gas_resistance"], fill="white")


def draw_curve(draw, data, maxy):
    """Draw a curve onto the draw object.

    @param draw: draw object to draw to
    @param data: array of data elements
    @param maxy: maximum y value to use
    """
    minv = min(data)
    maxv = max(data)
    span = float(maxv - minv)
    # Mirror vertically.
    mdata = [(1 - (i - minv) / span) * maxy for i in data]
    for x in range(len(mdata) - 1):
        draw.line([(x, mdata[x]), (x + 1, mdata[x + 1])], fill=1)


def display_elem_curve(draw, elem, data):
    """Draw a curve for an element in the data array

    @param draw: draw object
    @param elem: name of the elemnt
    @param data: data array, only the last 128 elements are used
    """
    if len(data) > 2:
        # Only get the last 128 elements and reverse. And select the
        # correct element.
        data = [i[elem] for i in data[-128:]]
        # Clear image.
        draw.rectangle([0, 0, 128, 64], fill=0)
        # Print header.
        draw.text((9, 53), elem, fill="white")
        draw_curve(draw, data, 56)


def main():
    """Main function without further arguments."""
    bme =  bme68x.BME68X(BME_I2C_ADDR, 0)
    disp = init_display()
    # Create a B/W image.
    image = Image.new('1', (128, 64))
    # Get drawing object to draw on image.
    draw = ImageDraw.Draw(image)
    # Get the default font.
    # font = ImageFont.load_default()
    i = 0
    try:
        global dataarr
        dataarr = json.load(open(DATASTOREFNAME))
        print("%d elements read." % len(dataarr))
    except IOError:
        pass
    collector_thread = threading.Thread(target=loop_new_env_data, name="thread-collector", args=(bme,))
    collector_thread.start()
    print("Collector id=%d." % collector_thread.ident)
    print('Press Ctrl-C to quit.')
    try:
        while True:
            image.putpixel((i % 128, 0), image.getpixel((i % 128, 0)) ^ 1)
            # Clear image.
            draw.rectangle([0, 1, 128, 64], fill=0)
            # Get latest data.
            data = dataarr[-1]
            print("Displaying overview.")
            display_data(data, draw)
            # Display image.
            disp.image(image)
            disp.display()
            time.sleep(7)
            i += 1
            for elem in ("temperature", "pressure", "humidity", "gas_resistance"):
                print("Displaying '%s'." % elem)
                display_elem_curve(draw, elem, dataarr)
                disp.image(image)
                disp.display()                
                time.sleep(4)
    except KeyboardInterrupt:
        print("Stopping data acquisition.")
        global RUNNING
        RUNNING = False
        disp.clear()
        disp.display()
        # Wait until other thread finishes.
        collector_thread.join()
        with open(DATASTOREFNAME, "w") as out:
            json.dump(dataarr, out)
        
    
if __name__ == "__main__":
    main()

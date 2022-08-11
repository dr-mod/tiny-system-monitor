import board
import busio
import displayio
import time
from adafruit_display_text import label
from adafruit_st7789 import ST7789
from bitmaptools import fill_region, draw_line
import terminalio
import usb_cdc
import math
import struct
import digitalio

activator = digitalio.DigitalInOut(board.GP22)
activator.direction = digitalio.Direction.OUTPUT
activator.value = True

def convert_size(size_bytes):
    if size_bytes == 0:
        return "0 b"
    size_name = ("b", "Kb", "Mb", "Gb", "Tb", "Pb", "Eb", "Zb", "Yb")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    d = round(size_bytes / p, 2)
    if i == 0:
        return "%d %s" % (d, size_name[i])
    else:
        return "%0.2f %s" % (d, size_name[i])


def calc_load(update_ms, update_span, old_load, target_load):
    diff_ms = abs(time.monotonic() - update_ms)
    if diff_ms > update_span:
        diff_ms = update_span
    glide = diff_ms / float(update_span)

    load_diff = target_load - old_load
    return old_load + load_diff * glide


class NetStat:
    def __init__(self, x, y, update_span=1.0):
        self.x = x
        self.y = y

        self.in_val = 0
        self.target_in_val = 0
        self.old_in_val = 0
        self.out_val = 0
        self.target_out_val = 0
        self.old_out_val = 0
        self.update_span = update_span
        self.update_ms = 0

        self.group = displayio.Group(x=x, y=y)
        network = label.Label(terminalio.FONT, text="Network", color=0xFFFFFF)
        network.x = 0
        network.y = 0
        self.in_text = label.Label(terminalio.FONT, text="in:  0b", color=0xFFFFFF)
        self.in_text.x = 0
        self.in_text.y = 10
        self.out_text = label.Label(terminalio.FONT, text="out: 0b", color=0xFFFFFF)
        self.out_text.x = 0
        self.out_text.y = 20
        self.group.append(network)
        self.group.append(self.in_text)
        self.group.append(self.out_text)

    def set_in_out(self, in_val, out_val):
        if in_val < 0:
            in_val = 0
        if out_val < 0:
            out_val = 0
        self.target_in_val = in_val
        self.target_out_val = out_val
        self.old_in_val = self.in_val
        self.old_out_val = self.out_val
        self.update_ms = time.monotonic()

    def tick(self):
        if (int(self.target_in_val) == int(self.in_val)) and (int(self.target_out_val) == int(self.out_val)):
            return
        self.out_val = calc_load(self.update_ms, self.update_span, self.old_out_val, self.target_out_val)
        self.in_val = calc_load(self.update_ms, self.update_span, self.old_in_val, self.target_in_val)
        self.out_text.text = "out: %s" % convert_size(self.out_val)
        self.in_text.text = "in:  %s" % convert_size(self.in_val)


class Gauge:
    BAR_HEIGHT = 133
    BAR_WIDTH = 27
    BAR_REDUCTION = 20

    HEAT_PALETTE = displayio.Palette(50)
    HEAT_PALETTE[48] = 0xFFFFFF
    color_range = len(HEAT_PALETTE) - 2
    for i in range(0, color_range):
        if i <= color_range / 2:
            g = int(255 * (i / float(color_range / 2)))
            HEAT_PALETTE[i] = (255, g, 0)
        else:
            r = int(255 - (255 * ((i - (color_range / 2)) / float(color_range / 2))))
            HEAT_PALETTE[i] = (r, 255, 0)

    HEAT_BMP = displayio.Bitmap(BAR_WIDTH - 2, BAR_HEIGHT - BAR_REDUCTION - 2, 49)
    for i in range(0, BAR_HEIGHT - BAR_REDUCTION - 2):
        draw_line(HEAT_BMP, 0,
                  i,
                  BAR_WIDTH - 3, i,
                  int((len(HEAT_PALETTE) - 2) * (i / (BAR_HEIGHT - BAR_REDUCTION - 2)))
                  # i % 48
                  )

    def __init__(self, x, y, caption, update_span=1.0):
        self.x = x
        self.y = y

        self.load = 1
        self.target_load = 0
        self.old_load = 0
        self.update_span = update_span
        self.update_ms = 0

        self.group = displayio.Group(x=x, y=y)
        self.bar_bitmap, color_sprite = self.bar()
        self.group.append(color_sprite)
        self.group.append(self.caption(caption))
        self.caption_l = self.caption_load()
        self.group.append(self.caption_l)

    def bar(self):
        color_bitmap = displayio.Bitmap(Gauge.BAR_WIDTH, Gauge.BAR_HEIGHT - Gauge.BAR_REDUCTION, 48)
        fill_region(color_bitmap, 0, 0, Gauge.BAR_WIDTH, Gauge.BAR_HEIGHT - Gauge.BAR_REDUCTION, 48)
        color_sprite = displayio.TileGrid(color_bitmap, pixel_shader=Gauge.HEAT_PALETTE, x=0, y=0)
        return color_bitmap, color_sprite

    def caption_load(self):
        text_area = label.Label(terminalio.FONT, text="0%", color=0xFFFFFF)
        text_area.x = int((Gauge.BAR_WIDTH - text_area.bounding_box[2]) / 2)
        text_area.y = Gauge.BAR_HEIGHT - 14
        return text_area

    def caption(self, caption):
        text_area = label.Label(terminalio.FONT, text=caption, color=0xFFFFFF)
        text_area.x = int((Gauge.BAR_WIDTH - text_area.bounding_box[2]) / 2)
        text_area.y = Gauge.BAR_HEIGHT - 4
        return text_area

    def set_load(self, level):
        if level > 100:
            level = 100
        elif level < 0:
            level = 0
        self.target_load = level
        self.old_load = self.load
        self.update_ms = time.monotonic()

    def get_graphics(self):
        return self.group

    def tick(self):
        if int(self.target_load) == int(self.load):
            return
        self.load = calc_load(self.update_ms, self.update_span, self.old_load, self.target_load)

        if self.load > 100:
            self.load = 100
        elif self.load < 0:
            self.load = 0
        fill_region(self.bar_bitmap, 0, 0, Gauge.BAR_WIDTH, Gauge.BAR_HEIGHT - Gauge.BAR_REDUCTION, 48)
        self.bar_bitmap.blit(1, 1, Gauge.HEAT_BMP)
        fill_region(self.bar_bitmap, 1, 1, Gauge.BAR_WIDTH - 1,
                    int((Gauge.BAR_HEIGHT - Gauge.BAR_REDUCTION - 2) * ((100 - (self.load)) / 100.0)) + 1, 49)
        self.caption_l.text = "%d%%" % int(self.load)
        self.caption_l.x = int((Gauge.BAR_WIDTH - self.caption_l.bounding_box[2]) / 2)


displayio.release_displays()

tft_cs = board.GP17
tft_dc = board.GP16
spi_mosi = board.GP19
spi_clk = board.GP18
spi = busio.SPI(spi_clk, spi_mosi)

display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs)
display = ST7789(
    display_bus, rotation=270, width=240, height=135, rowstart=40, colstart=53
)

main_group = displayio.Group()
display.show(main_group)
display.auto_refresh = False

g = Gauge(0, 0, "CPU")
g2 = Gauge(35, 0, "GPU")
g3 = Gauge(70, 0, "MEM", 0.001)
g4 = Gauge(105, 0, "SSD", 0.001)
main_group.append(g.get_graphics())
main_group.append(g2.get_graphics())
main_group.append(g3.get_graphics())
main_group.append(g4.get_graphics())

network = NetStat(141, 5)
main_group.append(network.group)

sensors = label.Label(terminalio.FONT, text="Temperature", color=0xFFFFFF)
sensors.x = 141
sensors.y = 45
sensors_cpu = label.Label(terminalio.FONT, text="CPU: 0C*", color=0xFFFFFF)
sensors_cpu.x = 141
sensors_cpu.y = 55

main_group.append(sensors)
main_group.append(sensors_cpu)

# g.set_load(100)
# g2.set_load(11)
# g3.set_load(52)
# g4.set_load(94)
# network.set_in_out(19224244, 5335)

tick_counter = 0
# for i in range(0, 500):
#     g.tick()
#     g2.tick()
#     g3.tick()
#     g4.tick()
#     if tick_counter % 4 == 0:
#         network.tick()
#     # time.sleep(0.01)
#     display.refresh()
#     tick_counter = tick_counter + 1
#     if tick_counter > 250:
#         tick_counter = 0


while True:
    try:
        available = usb_cdc.data.in_waiting
        while available >= 14:
            raw = usb_cdc.data.read(available)
            data = struct.unpack("bbbbIIf", raw)
            g.set_load(data[0])
            g2.set_load(data[1])
            g3.set_load(data[2])
            g4.set_load(data[3])
            network.set_in_out(data[4], data[5])
            sensors_cpu.text = "CPU: %d c*" % data[6]
            available = usb_cdc.data.in_waiting
        g.tick()
        g2.tick()
        g3.tick()
        g4.tick()
        display.refresh()
        if tick_counter % 4 == 0:
            network.tick()
    except:
        pass

while True:
    pass

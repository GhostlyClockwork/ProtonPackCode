# MIT License

# Copyright (c) 2024 GhostlyClockwork and Mike Buland

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.



import digitalio
import time
import board
import neopixel
import math
import random

# import audiocore

from audiocore import WaveFile
from adafruit_debouncer import Debouncer
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.solid import Solid
from adafruit_led_animation.helper import PixelSubset, PixelMap


class ReversePixelSubset(PixelMap):
    def __init__(self, pixel_object, start, end):
        super().__init__(
            pixel_object,
            pixel_ranges=[[n] for n in range(end - 1, start - 1, -1)],
            individual_pixels=True,
        )


switch1 = digitalio.DigitalInOut(board.D9)
switch1.switch_to_input(digitalio.Pull.UP)  # pull up: HIGH / True is unpressed
dbswitch1 = Debouncer(switch1)
switch2 = digitalio.DigitalInOut(board.D13)
switch2.switch_to_input(digitalio.Pull.UP)
dbswitch2 = Debouncer(switch2)

try:
    from audioio import AudioOut
except ImportError:
    try:
        from audiopwmio import PWMAudioOut as AudioOut
    except ImportError:
        pass  # not always supported by every board!

HUM_LOOP = WaveFile(open("Afterlife_hum_loop_01.wav", "rb"))  # Change to the name of your wav file!
START = WaveFile(open("Afterlife_pack_startup.wav", "rb"))
WAND_START = WaveFile(open("Afterlife_thrower.wav", "rb"))
BEAM_LOOP = WaveFile(open("Afterlife_protongun_beam_contain_loop.wav", "rb"))
BEAM_START = WaveFile(open("Afterlife_protongun_beam_contain_start.wav", "rb"))
BEAM_STOP = WaveFile(open("Afterlife_protongun_shutdown.wav", "rb"))

audio = AudioOut(board.A0)


enable = digitalio.DigitalInOut(board.D10)
enable.direction = digitalio.Direction.OUTPUT
enable.value = True

NUM_PIXELS = 22
BAR_NUM = 16
WAND_NUM = 2
NEOPIXEL_PIN = board.D5
BAR = board.D11
RING_PIN = board.D12

POWER_PIN = board.D10
ONSWITCH_PIN = board.A1


strip = neopixel.NeoPixel(
    NEOPIXEL_PIN, NUM_PIXELS, brightness=1, auto_write=False, pixel_order=neopixel.GRBW
)

proton_strip = (
    PixelSubset(strip, 2, 7),
    ReversePixelSubset(strip, 7, 12),
    PixelSubset(strip, 12, 17),
    ReversePixelSubset(strip, 17, 22),
)

strip2 = neopixel.NeoPixel(BAR, BAR_NUM, brightness=1.0, auto_write=False)

ring_strip = neopixel.NeoPixel(
    RING_PIN, 60, brightness=1.0, auto_write=False, pixel_order=neopixel.GRBW
)

cyclotron = Comet(
    ring_strip,
    speed=0.01,
    color=(255, 0, 0),
    tail_length=5,
    ring=True,
    bounce=False,
)

wand_strip = PixelSubset(strip, 0, 2)


class Animation:
    def __init__(self, strip, timeinc, shower=None):
        self.timeinc = timeinc
        self.last_update = 0  # when we last updated
        self.strip = strip
        if shower is None:
            self.shower = strip
        else:
            self.shower = shower

    def update(self):
        curtime = time.monotonic()
        if curtime - self.last_update > self.timeinc:
            self._update(curtime)
            self.shower.show()
            self.last_update = curtime

    def _update(self, curtime):
        pass


class LEDFill(Animation):
    def __init__(self, strip, hue, timeinc):
        super().__init__(strip, timeinc)
        self.hue = hue  # what color we are
        self.pos = 0  # where on the ring we are

    def _update(self, curtime):
        self.strip[self.pos] = self.hue
        self.pos += 1
        if self.pos == len(self.strip):
            self.pos = 0
            self.strip.fill(0)

class ProtonBeam(Animation):
    def __init__(self, strip, timeinc, shower):
        super().__init__(strip, timeinc, shower)
        self.curscale = 1.0
        self.offset = 0

    def off(self):
        for pix in self.strip:
            for i in range(0, len(pix)):
                pix[i] = (0,0,0,0)
            pix.show()

    def _update(self, curtime):
        for pix in self.strip:
            for i in range(0, len(pix)):
                b = math.sin((i * 0.5) - self.offset * 0.75)
                if b > 0.8 and random.random() > 0.2:
                    pix[i] = (0, 0, 190 + int((random.random() - 0.5) * 30))
                else:
                    g = min(
                        max(
                            35
                            + (
                                math.sin((i * 0.5) + self.offset)
                                + math.sin((i * 1.77) + self.offset * 1.271)
                            )
                            * 65
                            * self.curscale,
                            35,
                        ),
                        100,
                    )
                    pix[i] = (250, g, 0)

        # A good orange: (250, 35, 0)
        # A good yellow: (250, 100, 0)
        self.offset += (self.last_update - curtime) * 10.0

class StateManager:
    def __init__(self):
        self.states = {}
        self.curState = None
        self.nextState = None

    def addState(self, name, state):
        self.states[name] = state

    def queueState(self, name):
        print("requested " + name)
        if self.curState is None:
            self.curState = self.states[name]
            self.curState.entered(self)
        else:
            self.nextState = self.states[name]

    def update(self):
        if self.curState is None:
            self.curState = self.nextState
            self.nextState = None
            if not self.curState is None:
                self.curState.entered(self)
        elif not self.nextState is None:
            self.curState.exited(self)
            self.curState = self.nextState
            self.nextState = None
            self.curState.entered(self)
        if not self.curState is None:
            self.curState.update( self )

class State:
    def __init__(self):
        pass

    def entered(self, manager):
        pass

    def exited(self, manager):
        pass

    def update(self, manager):
        pass

class StatePowerOn(State):
    def entered(self, manager):
        audio.play(START)

    def exited(self, manager):
        pass

    def update(self, manager):
        if not audio.playing:
            manager.queueState("idle")
        cyclotron.animate()
        barGraph.update()

class StateIdle(State):
    def entered(self, manager):
        audio.play(HUM_LOOP)
        for i in range(0, len(wand_strip)):
            wand_strip[i] = (0,0,0)
        wand_strip.show()

    def exited(self, manager):
        pass

    def update(self, manager):
        if not audio.playing:
            audio.play(HUM_LOOP)
        cyclotron.animate()
        barGraph.update()
        dbswitch1.update()
        if dbswitch1.fell:
            manager.queueState("wandPowerUp")

class StateWandPowerUp(State):
    def entered(self, manager):
        audio.play(WAND_START)
        for i in range(0, len(wand_strip)):
            wand_strip[i] = (255,255,255)
        wand_strip.show()

    def update(self, manager):
        if not audio.playing:
            manager.queueState("wandPowerOn")
        cyclotron.animate()
        barGraph.update()
        dbswitch1.update()
        dbswitch2.update()
        if dbswitch1.rose:
            manager.queueState("idle")
        if dbswitch2.fell:
            manager.queueState("beamStart")

class StateWandPowerOn(State):
    def entered(self, manager):
        audio.play(HUM_LOOP)
        for i in range(0, len(wand_strip)):
            wand_strip[i] = (255,255,255)
        wand_strip.show()

    def update(self, manager):
        if not audio.playing:
            audio.play(HUM_LOOP)
        cyclotron.animate()
        barGraph.update()
        dbswitch1.update()
        dbswitch2.update()
        if dbswitch1.rose:
            manager.queueState("idle")
        if dbswitch2.fell:
            manager.queueState("beamStart")

class StateBeamStart(State):
    def entered(self, manager):
        audio.play(BEAM_START)

    def update(self, manager):
        if not audio.playing:
            manager.queueState("beamRun")
        cyclotron.animate()
        barGraph.update()
        proton.update()

class StateBeamRun(State):
    def entered(self, manager):
        audio.play(BEAM_LOOP)

    def update(self, manager):
        if not audio.playing:
            audio.play(BEAM_LOOP)
        cyclotron.animate()
        barGraph.update()
        dbswitch2.update()
        proton.update()
        if dbswitch2.rose:
            proton.off()
            manager.queueState("beamStop")

class StateBeamStop(State):
    def entered(self, manager):
        audio.play(BEAM_STOP)

    def update(self, manager):
        cyclotron.animate()
        barGraph.update()
        if not audio.playing:
            manager.queueState("wandPowerOn")

manager = StateManager()
manager.addState("powerOn", StatePowerOn())
manager.addState("idle", StateIdle())
manager.addState("wandPowerUp", StateWandPowerUp())
manager.addState("wandPowerOn", StateWandPowerOn())
manager.addState("beamStart", StateBeamStart())
manager.addState("beamRun", StateBeamRun())
manager.addState("beamStop", StateBeamStop())
manager.queueState("powerOn")
# ledfill = LEDFill(strip2, 0x0000FF, 0.03)
proton = ProtonBeam(proton_strip, 0.03, strip)
barGraph = LEDFill(strip2, (0,0,255), 0.03)

last_print = 0

#audio.play(START)
while True:
    manager.update()
    #cyclotron.animate()
    #barGraph.update()
    #proton.update()

"""Roll dice on a Raspberry Pi.

1. Prepare empty rolling chamber.
2. Run this script. One roll is performed to settle the rolling machine,
    reference photo is taken.
3. Add die to chamber.
4. Press enter, NUM_ROLLS rolls are performed for analysis.
"""

# GPIO pin numbers
PIN_LEDS = 17
PIN_SERVO = 18

GROUP = 'capture'
NUM_ROLLS = 3000
START_NUM = 0  # Starting > 0 skips the reference photo.

SERVO_SHAKE_US = 930
SERVO_UPRIGHT_US = 2150

SHUTTER_SEC = 1.0 / 3.0
ISO = 200

# From https://github.com/Gadgetoid/WiringPi2-Python .
# sudo apt-get install python-setuptools
# sudo pip install RPIO
# RPIO is preferred to GPIO for hardware PWM for servo control.
# Software PWM jitters and occasionally stops at the wrong location.
import RPIO
import RPIO.PWM
RPIO.PWM.set_loglevel(RPIO.PWM.LOG_LEVEL_ERRORS)

import picamera

import os
import time


def RollDie(servo):
  servo.set_servo(PIN_SERVO, SERVO_SHAKE_US)
  time.sleep(1.0)
  servo.set_servo(PIN_SERVO, SERVO_UPRIGHT_US)
  time.sleep(1.0)


def TakePicture(group_name, picture_local_name):
  picture_name = os.path.join(group_name, picture_local_name)
  # Having the camera open makes PWM much shakier, so open it only for the
  # duration of the picture.
  with picamera.PiCamera() as camera:
    # http://picamera.readthedocs.org/en/release-1.10/api_camera.html
    camera.resolution = (2592, 1944)
    #camera.resolution = (1296, 972)
    camera.zoom = (0.0, 0.0, 1.0, 1.0)  # x, y, w, h
    camera.framerate = 1.0 / SHUTTER_SEC  # controls allowable shutter speeds
    camera.awb_mode = 'off'
    camera.awb_gains = (1.52, 1.43)
    camera.iso = ISO  # ISO does nothing if set after shutter.
    camera.shutter_speed = long(SHUTTER_SEC * 1000000)
    RPIO.output(PIN_LEDS, True)
    camera.capture(picture_name, quality=10)
  RPIO.output(PIN_LEDS, False)
  return picture_name


if __name__ == '__main__':
  if not os.path.exists(GROUP):
    os.makedirs(GROUP)
  RPIO.setup(PIN_LEDS, RPIO.OUT)
  servo = RPIO.PWM.Servo()

  try:
    if START_NUM <= 0:
      RollDie(servo)
      reference_name = TakePicture(GROUP, 'reference.JPG')
      print 'Took reference: %s' % reference_name
      raw_input('Press enter to continue. ')
    i = START_NUM
    errors = 0
    while i < NUM_ROLLS and errors < 10:
      RollDie(servo)
      try:
        picture_name = TakePicture(GROUP, '%05d.JPG' % i)
        print '%d/%d\t%s' % (i + 1, NUM_ROLLS, picture_name)
        i += 1
      except picamera.exc.PiCameraRuntimeError, e:
        print e
        errors += 1
  except KeyboardInterrupt, e:
    print 'stopping'
  RPIO.cleanup()

"""Roll dice on a Raspberry Pi.

1. Prepare empty rolling chamber.
2. Run this script. One roll is performed to settle the rolling machine,
    reference photo is taken.
3. Add die to chamber.
4. Press enter, NUM_ROLLS rolls are performed for analysis.
"""

PIN_LEDS = 17
PIN_SERVO = 18

GROUP = 'capture'
NUM_ROLLS = 3000
START_NUM = 0  # Starting > 0 skips the reference photo.

ANGLE_SHAKE = 45.0
ANGLE_UPRIGHT = 180.0

SHUTTER_SEC = 1.0 / 3.0
ISO = 200

import RPi.GPIO as GPIO
import picamera

import os
import time


def SetUp():
  if not os.path.exists(GROUP):
    os.makedirs(GROUP)
  GPIO.setmode(GPIO.BCM)
  GPIO.setup(PIN_LEDS, GPIO.OUT)
  GPIO.setup(PIN_SERVO, GPIO.OUT)

  # http://sourceforge.net/p/raspberry-gpio-python/wiki/PWM/
  pwm = GPIO.PWM(PIN_SERVO, 100)  # 100 Hz.
  pwm.start(0.0)  # Initial duty cycle of 0 (always off).
  return pwm


def RollDie(pwm):
  MoveServo(pwm, ANGLE_SHAKE)
  time.sleep(0.5)
  MoveServo(pwm, ANGLE_UPRIGHT)
  time.sleep(0.5)


def MoveServo(pwm, angle):
  # Using ChangeDutyCycle(0.0) instead of start() and stop() is a workaround
  # for a bug in the Pi PWM where it creates new threads for each start() and
  # hits the per-process thread limit. See
  # http://sourceforge.net/p/raspberry-gpio-python/tickets/94/ via
  # http://raspberrypi.stackexchange.com/questions/40126 .
  pwm.ChangeDutyCycle(angle / 10.0 + 2.5)
  time.sleep(0.5)
  pwm.ChangeDutyCycle(0.0)


def TakePicture(group_name, picture_local_name):
  GPIO.output(PIN_LEDS, GPIO.HIGH)
  picture_name = os.path.join(group_name, picture_local_name)
  # Having the camera open makes PWM much shakier, so open it only for the
  # duration of the picture.
  with picamera.PiCamera() as camera:
    # http://picamera.readthedocs.org/en/release-1.10/api_camera.html
    camera.resolution = (2592, 1944)
    #camera.resolution = (1296, 972)
    camera.zoom = (0.0, 0.0, 1.0, 1.0)  # x, y, w, h
    camera.framerate = 1.0 / SHUTTER_SEC  # controls the allowable shutter speeds
    camera.awb_mode = 'off'
    camera.awb_gains = (1.52, 1.43)
    camera.iso = ISO  # ISO does nothing if set after shutter.
    camera.shutter_speed = long(SHUTTER_SEC * 1000000)
    camera.capture(picture_name, quality=10)
  GPIO.output(PIN_LEDS, GPIO.LOW)
  return picture_name


if __name__ == '__main__':
  pwm = SetUp()
  try:
    if START_NUM <= 0:
      RollDie(pwm)
      reference_name = TakePicture(GROUP, 'reference.JPG')
      print 'Took reference: %s' % reference_name
      raw_input('Press enter to continue. ')
    i = START_NUM
    errors = 0
    while i < NUM_ROLLS and errors < 10:
      RollDie(pwm)
      try:
        picture_name = TakePicture(GROUP, '%05d.JPG' % i)
        print '%d/%d\t%s' % (i + 1, NUM_ROLLS, picture_name)
        i += 1
      except picamera.exc.PiCameraRuntimeError, e:
        print e
        errors += 1
  except KeyboardInterrupt, e:
    print 'stopping'
  pwm.stop()

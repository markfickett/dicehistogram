"""Roll dice on a Raspberry Pi."""

PIN_LEDS = 17
PIN_SERVO = 18

GROUP = 'capture'
NUM_ROLLS = 50

ANGLE_SHAKE = 45.0
ANGLE_UPRIGHT = 175.0

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

def RollDie():
  MoveServo(ANGLE_SHAKE)
  time.sleep(0.8)
  MoveServo(ANGLE_UPRIGHT)
  time.sleep(1.0)


def MoveServo(angle):
  pwm = GPIO.PWM(PIN_SERVO, 100)  # What is 100 here?
  pwm.start(100)
  pwm.ChangeDutyCycle(angle / 10.0 + 2.5)
  time.sleep(0.2)
  pwm.stop()


def TakePicture(group_name, picture_local_name):
  GPIO.output(PIN_LEDS, GPIO.HIGH)
  picture_name = os.path.join(group_name, picture_local_name)
  # Having the camera open makes PWM much shakier, so open it only for the
  # duration of the picture.
  with picamera.PiCamera() as camera:
    camera.resolution = (2592, 1944)
    #camera.resolution = (1296, 972)
    camera.zoom = (0.0, 0.0, 1.0, 1.0)  # x, y, w, h
    camera.framerate = 5.0  # controls the allowable shutter speeds
    camera.exposure_mode = 'off'
    camera.awb_mode = 'off'
    camera.awb_gains = (1.52, 1.43)
    camera.shutter_speed = long(1.0/4.0 * 1000000)  # microseconds
    camera.iso = 100
    camera.capture(picture_name, quality=98)
  GPIO.output(PIN_LEDS, GPIO.LOW)
  return picture_name


if __name__ == '__main__':
  SetUp()
  RollDie()
  reference_name = TakePicture(GROUP, 'reference.JPG')
  print 'Took reference: %s' % reference_name
  raw_input('Press enter to continue. ')
  for i in xrange(NUM_ROLLS):
    RollDie()
    picture_name = TakePicture(GROUP, '%05d.JPG' % i)
    print '%d/%d\t%s' % (i + 1, NUM_ROLLS, picture_name)

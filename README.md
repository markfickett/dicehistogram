# How Fair Is My D20?

An automatic system for rolling a polyhedral die and taking photos of the rolls; extracting the image of just the die from those images; clustering the images of the die by which face is shown; and analyzing the results.

I was inspired in part by the [Awesome Dice Blog's 2012 post](http://www.awesomedice.com/blog/353/d20-dice-randomness-test-chessex-vs-gamescience/) comparing d20 fairness between two manufacturers. They rolled and tallied by hand.

## Results

TODO

## Hardware Setup (Die Roller and Camera)

[video TODO]

A microcontroller runs a servo motor to shake a small tub, and triggers a camera to take pictures. The microcontroller is an ATtiny85 running [a short Arduino sketch](#TODO). The camera is a D90 with a [3D-printed AC adapter plug](#TODO) and a [repaired wired-remote port](#TODO). All are powered by an ATX PSU (with a [9v regulator](#TODO) for the camera).

Thanks to [Chris Wren](https://plus.google.com/+ChrisWren) for inspiration on this mechanism.

TODO rate of rolls/photographs

## Software Workflow (How To Use these Scripts)

TODO
mkdir
crop (adjust scan distance)
group (adjust threshold)
summarize (label)

## Software Explanation

There are two computer-vision tasks in this process: finding the die within the larger photo of the die-rolling area; and figuring out which picture is of which face of the die.

### Cropping

TODO scan, sliding window / caveats, flood-fill

### Clustering

TODO feature extraction / matching, (re)grouping

## Dependencies

* [Python Imaging Library (PIL)](http://www.pythonware.com/products/pil/) for extracting the die from raw imagery and building a summary image
* [OpenCV](http://docs.opencv.org/doc/tutorials/introduction/linux_install/linux_install.html)
  * for feature extraction and matching, to cluster images of die faces
  * requires [CMake](https://cmake.org/install/) and other libraries (some of which its CMake build will install automatically)

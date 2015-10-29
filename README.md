# D20 Roll Fairness Evaluation

Scripts for extracting the image of just the die from automatically taken images; clustering the images of the die by which face is shown; and analyzing the results.

[Full project details, algorithm overview, and results](TODO).

## Example Results

Analysis produces a histogram of rolls like this summary of a Chessex Gemini Copper-Steel d20:

```
N=2397 normalized stddev=0.16 min=0.73 max=1.29 expected=10.30
   1 0.90 =============================================
   2 1.08 =================================================*====
   3 1.18 =================================================*========
   4 1.25 =================================================*============
   5 0.81 ========================================
   6 0.88 ============================================
   7 0.77 ======================================
   8 1.06 =================================================*==
   9 1.17 =================================================*========
  10 1.17 =================================================*========
  11 1.29 =================================================*==============
  12 1.06 =================================================*==
  13 0.90 =============================================
  14 0.95 ===============================================
  15 0.87 ===========================================
  16 0.73 ====================================
  17 1.08 =================================================*====
  18 0.94 ===============================================
  19 1.00 =================================================*
  20 0.89 ============================================
```

## How To Use these Scripts

TODO
mkdir
crop (adjust scan distance)
group (adjust threshold)
summarize (label)

## Dependencies

* [Python Imaging Library (PIL)](http://www.pythonware.com/products/pil/) for extracting the die from raw imagery and building a summary image
* [OpenCV](http://docs.opencv.org/doc/tutorials/introduction/linux_install/linux_install.html)
  * for feature extraction and matching, to cluster images of die faces
  * requires [CMake](https://cmake.org/install/) and other libraries (some of which its CMake build will install automatically)

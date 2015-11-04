# D20 Roll Fairness Evaluation

Scripts for extracting the image of just the die from automatically taken images; clustering the images of the die by which face is shown; and analyzing the results.

[Full project details, algorithm overview, and results](http://www.markfickett.com/stuff/artPage.php?id=389).

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

For example, processing an opaque purple Chessex d6, you might do:

```shell
DATA=data/chessexopaquepurple
mkdir -p $DATA
mkdir -p $DATA/capture
cp path/to/camera/*.JPG $DATA/capture
./crop.py $DATA  # produces $DATA/crop
./group.py $DATA  # processes from $DATA/crop, writes $DATA/summary.(jpg|json)
```

Often the default thresholds won't be exactly right. The `group.py` script prints its PID for convenience; you can `kill -HUP $PID` to get an intermediate summary image, or type `^C` to stop processing and write partial results. If there miscategorized images in a row, adjust the threshold to be above those images' match count. If there are too many groups, look at the representative image (far left in the summary image) and adjust the threshold below its match count.

```shell
./group.py $DATA --match-count-threshold 36
```

Finally, provide labels (reading the numbers on the die images down the left edge of the summary image) to generate a summary. For this example, the first row in the summary image (or the first sub-list in `summary.json`) is from images of the 5 on the die, the next is of 6s, and so on (with 1 and 6 seeing some repeated rows due to poor matches).

```shell
./summarize.py $DATA 5 6 4 1 2 1 1 3 1 1 6 1
```

## Dependencies

* [Python Imaging Library (PIL)](http://www.pythonware.com/products/pil/) for extracting the die from raw imagery and building a summary image
* [OpenCV](http://docs.opencv.org/doc/tutorials/introduction/linux_install/linux_install.html)
  * for feature extraction and matching, to cluster images of die faces
  * requires [CMake](https://cmake.org/install/) and other libraries (some of which its CMake build will install automatically)

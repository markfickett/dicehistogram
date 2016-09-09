# D20 Roll Fairness Evaluation

Scripts for extracting the image of just the die from automatically taken images; clustering the images of the die by which face is shown; and analyzing the results.

[Full project details, algorithm overview, and results](http://www.markfickett.com/dice).

## Example Results

Analysis produces a histogram of rolls like this summary of a Chessex Gemini
Copper-Steel d20. The graph shows 95% confidence intervals, and (*) highlights
the "fair" value. For example, on this die 5s come up 4.0% of the time which is
significantly lower than the 5.0% that would be fair.

```
N=2397 p=0.000007 (0% chance the data is from a random source)
per-side probabilities: stddev=0.008 min=0.037 max=0.065 fair=0.050
expected=10.30
 1 0.045 ==================================<=======x====*>
 2 0.054 ===========================================<===*===x======>
 3 0.059 ===============================================*<======x=======>
 4 0.063 ===============================================*===<=======x=======>
 5 0.040 ==============================<======x======>
 6 0.044 ==================================<======x=====*>
 7 0.038 ============================<======x======>
 8 0.053 ==========================================<====*=x=======>
 9 0.058 ===============================================<=======x======>
10 0.058 ===============================================<=======x=======>
11 0.065 ===============================================*=====<=======x========>
12 0.053 ==========================================<====*=x=======>
13 0.045 ==================================<=======x====*>
14 0.048 =====================================<======x==*====>
15 0.043 ==================================<=====x======>
16 0.037 ===========================<=====x======>
17 0.054 ===========================================<===*===x======>
18 0.047 =====================================<======x==*===>
19 0.050 =======================================<=======x======>
20 0.045 ==================================<======x=====*>
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

Often the default threshold won't be exactly right. The `group.py` script prints its PID for convenience; you can `kill -HUP $PID` to get an intermediate summary image, or type `^C` to stop processing and write partial results. If there are too many groups, look at the representative image (far left in the summary image) and adjust the threshold below its match count, for example `--match-count 22`. If there miscategorized images in a row, adjust the threshold to be above those images' match count. (1s and 7s are often adjacent on the die and get matched erroneously when the threshold is too low.)

```shell
./group.py $DATA --match-count-threshold 36
```

Next, provide labels (reading the numbers on the die images down the left edge of the summary image) to generate a summary. For this example, the first row in the summary image (or the first sub-list in `summary.json`) is from images of the 5 on the die, the next is of 6s, and so on (with 1 and 6 seeing some repeated rows due to poor matches).

```shell
./label.py $DATA 5 6 4 1 2 1 1 3 1 1 6 1
```

Finally, analyze the sequence of labels.

```shell
./summarize.py $DATA
```

## Dependencies

* [Python Imaging Library (PIL)](http://www.pythonware.com/products/pil/) for extracting the die from raw imagery and building a summary image
* [OpenCV](http://docs.opencv.org/doc/tutorials/introduction/linux_install/linux_install.html)
  * for feature extraction and matching, to cluster images of die faces
  * requires [CMake](https://cmake.org/install/) and other libraries (some of which its CMake build will install automatically)

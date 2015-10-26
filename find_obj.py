#!/usr/bin/env python
"""
Feature-based image matching sample.

USAGE
  find_obj.py <image1> <image2>
"""

import cv2
import numpy
import sys


def init_feature():
    detector = cv2.ORB_create(400)
    norm = cv2.NORM_HAMMING
    matcher = cv2.BFMatcher(norm)
    return detector, matcher


def filter_matches(kp1, kp2, matches, ratio = 0.75):
    mkp1, mkp2 = [], []
    for m in matches:
        if len(m) == 2 and m[0].distance < m[1].distance * ratio:
            m = m[0]
            mkp1.append( kp1[m.queryIdx] )
            mkp2.append( kp2[m.trainIdx] )
    p1 = numpy.float32([kp.pt for kp in mkp1])
    p2 = numpy.float32([kp.pt for kp in mkp2])
    kp_pairs = zip(mkp1, mkp2)
    return p1, p2, kp_pairs



if __name__ == '__main__':
    print __doc__

    fn1, fn2 = sys.argv[1:]
    img1 = cv2.imread(fn1, 0)
    img2 = cv2.imread(fn2, 0)
    detector, matcher = init_feature()

    if img1 is None:
        print 'Failed to load fn1:', fn1
        sys.exit(1)

    if img2 is None:
        print 'Failed to load fn2:', fn2
        sys.exit(1)

    if detector is None:
        print 'unknown feature'
        sys.exit(1)

    kp1, desc1 = detector.detectAndCompute(img1, None)
    kp2, desc2 = detector.detectAndCompute(img2, None)
    print 'img1 - %d features, img2 - %d features' % (len(kp1), len(kp2))

    print 'matching...'
    raw_matches = matcher.knnMatch(desc1, trainDescriptors = desc2, k = 2) #2
    p1, p2, kp_pairs = filter_matches(kp1, kp2, raw_matches)
    print len(p1), len(p2)
    if len(p1) >= 4:
        H, status = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)
        if status is None:
          print 'no homography found'
        else:
          print '%d / %d  inliers/matched' % (numpy.sum(status), len(status))
    else:
        H, status = None, None
        print '%d matches found, not enough for homography estimation' % len(p1)

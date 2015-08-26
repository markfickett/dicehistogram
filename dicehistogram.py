import sys

sys.path.append('~/mwf/gitclients/experimental-mwf/google3/blaze-bin/third_party/py/PIL/selftest.runfiles/google3/third_party/py/')

import PIL
import PIL.Image

image = PIL.Image.open('/tmp/die.jpg')
print image.mode, image.size, image.format
h, w = image.size

image_data = image.getdata()
out_image = PIL.Image.new(image.mode, image.size)

tenths = (h * w) / 10
matched_x = set()
matched_y = set()
for n, (r, g, b) in enumerate(image_data):
  y = n / h
  x = n % h
  if n % tenths == 0:
    print (x, y)
  if max(r, b) > g:
    out_image.putpixel((x, y), (r, g, b))
    matched_x.add(x)
    matched_y.add(y)
  #else:
  #  out_image.putpixel((x, y), (0, g, 0))

bound = (min(matched_x), min(matched_y), max(matched_x), max(matched_y))
print bound
out_image = out_image.crop(bound)
print out_image.size
out_image.save('/tmp/example_output.png')
out_image.show()

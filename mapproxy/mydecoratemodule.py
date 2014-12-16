from mapproxy.image import ImageSource
from PIL import Image

import os
try:
  import numpy as np 
  import cv2
except ImportError:
  pass



def annotate_img(image, service, layers, environ, query_extent, **kw):
    try:
       if "oppai" in layers[0]:
          img = image.as_image()   #.convert('LA')
          img = np.asarray(img)
          file = os.getcwd() + os.sep + ".."+ os.sep + "haarcascade_upperbody.xml"
          cascade = cv2.CascadeClassifier(file)
          facerect = cascade.detectMultiScale(img, scaleFactor=1.2, minNeighbors=1, minSize=(30, 30))
          print "Oppai detect:"
          print facerect
          color = (0, 0, 0)
          if len(facerect) > 0:
             for rect in facerect:
                 cv2.rectangle(img, tuple(rect[0:2]),tuple(rect[0:2]+rect[2:4]), color, thickness=2)

          return ImageSource(Image.fromarray(np.uint8(img)),image.image_opts)
       else:
          return image
    except:
       return image

class RequestInfoFilter(object):
    """
    Simple MapProxy decorate_img middleware.

    Annotates map images with information about the request.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Add the callback to the WSGI environment
        environ['mapproxy.decorate_img'] = annotate_img

        return self.app(environ, start_response)
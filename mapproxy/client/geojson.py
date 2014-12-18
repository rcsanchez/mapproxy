# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mapproxy.client.http import retrieve_image
from mapproxy.image import ImageSource
from mapproxy.layer import BlankImage
from mapproxy.compat import BytesIO

import urllib2
from PIL import Image
try:
  import mapnik
  import tempfile
  import os
except ImportError:
  pass
try:
  import numpy as np
  from numpy import pi,arctan,sqrt,arctan2,sin,cos
  import scipy.ndimage
except ImportError:
  pass

class GeojsonClient(object):
    def __init__(self, url_template, http_client=None, grid=None, style=None):
        self.url_template = url_template
        self.http_client = http_client
        self.grid = grid
        self.style = style

    def get_tile(self, tile_coord, format=None):
       
        url = self.url_template.substitute(tile_coord, format, self.grid)
        if self.http_client:
            if ".txt" in url:
               return self.dem2shade(url,tile_coord)
            return self.mapnik_image(url,tile_coord)
        else:
            return retrieve_image(url)
    
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.url_template)

    def dem2shade(self,url,tile_coord):
        print url
        tx = tile_coord[0]
        ty = tile_coord[1]
        tz = tile_coord[2]
        z = max(0,min(tz,14))
        x, xd = divmod(tx,2**(tz-z))
        y, yd = divmod(ty,2**(tz-z))
        url = url.replace("/" + str(tx) + "/", "/" + str(x) + "/").replace("/" + str(ty) + ".txt", "/" + str(y) + ".txt").replace("/" + str(tz) + "/", "/" + str(z) + "/")
        try:
          response = urllib2.urlopen(url)
          data = response.read()
          data = data.replace("e","0")
          dem = np.array([row.split(',') for row in data.splitlines()],dtype=np.float32)
        
          TSIZE = 20037508.342789244
        
          size = TSIZE / 2 ** (z - 1)
          res = size/256.
          ulx = -TSIZE + size*x
          uly = TSIZE - size*y
          zscale=5
          azimuth=225
          angle_altitude=45
        
          x, y = np.gradient(dem*zscale,res,-res)  
          slope = pi/2. - arctan(sqrt(x*x + y*y))  
          aspect = arctan2(-x, y)  
          azimuthrad = azimuth*pi / 180.  
          altituderad = angle_altitude*pi / 180.
          shaded = sin(altituderad) * sin(slope) + cos(altituderad) * cos(slope) * cos(azimuthrad - aspect)  
          shaded = 255*(shaded + 1)/2
          sx = xd * 256/2**(tz-z)
          ex = (xd+1)* 256/2**(tz-z)
          sy = yd * 256/2**(tz-z)
          ey = (yd+1)* 256/2**(tz-z)
          shaded = shaded[sy:ey,sx:ex]
          shaded = scipy.ndimage.zoom(shaded, 2**(tz-z), order=0)
          img = Image.fromarray(np.uint8(shaded))
          return ImageSource(img)
        except: 
          raise BlankImage()
    def mapnik_image(self,url,tile_coord):
        print url
        x = str(tile_coord[0])
        y = str(tile_coord[1])
        z = str(tile_coord[2])

        try:
          response = urllib2.urlopen(url)
          html = response.read()
          f_geojson = tempfile.NamedTemporaryFile(delete=False)
          #f_geojson = open(os.getcwd() + "/../project/cache_data/" + x + y + z + '.json','w')
          if '\\u' in  html:
             html = html.decode('unicode_escape').encode('utf-8')
          f_geojson.write(html)
          f_geojson.close()
          #print f_geojson.name
          ds = mapnik.GeoJSON(file=f_geojson.name)
          os.unlink(f_geojson.name)
          stylesheet = self.style
          m = mapnik.Map(256,256)
          mapnik.load_map(m, stylesheet)
          s =  m.find_style('mapproxy')
          m.remove_all() #remove layer
          m.append_style('mapproxy',s)
          layer = mapnik.Layer('world',"+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs")
          layer.datasource = ds
          layer.styles.append('mapproxy')
          m.layers.append(layer)
          #m.background = mapnik.Color('rgb(255,255,255,0)')
          m.zoom_all()
          img = mapnik.Image(256, 256)
          mapnik.render(m,img)
          data = img.tostring("png")
          return ImageSource(BytesIO(data))
        except Exception as e:
          print e.message
          print "no mapnik"
          raise BlankImage()

class TileURLTemplate(object):
    """
    >>> t = TileURLTemplate('http://foo/tiles/%(z)s/%(x)d/%(y)s.png')
    >>> t.substitute((7, 4, 3))
    'http://foo/tiles/3/7/4.png'

    >>> t = TileURLTemplate('http://foo/tiles/%(z)s/%(x)d/%(y)s.png')
    >>> t.substitute((7, 4, 3))
    'http://foo/tiles/3/7/4.png'

    >>> t = TileURLTemplate('http://foo/tiles/%(tc_path)s.png')
    >>> t.substitute((7, 4, 3))
    'http://foo/tiles/03/000/000/007/000/000/004.png'
    
    >>> t = TileURLTemplate('http://foo/tms/1.0.0/%(tms_path)s.%(format)s')
    >>> t.substitute((7, 4, 3))
    'http://foo/tms/1.0.0/3/7/4.png'
    
    >>> t = TileURLTemplate('http://foo/tms/1.0.0/lyr/%(tms_path)s.%(format)s')
    >>> t.substitute((7, 4, 3), 'jpeg')
    'http://foo/tms/1.0.0/lyr/3/7/4.jpeg'
    
    """
    def __init__(self, template, format='geojson'):
        self.template= template
        self.format = format
        self.with_quadkey = True if '%(quadkey)' in template else False
        self.with_tc_path = True if '%(tc_path)' in template else False
        self.with_tms_path = True if '%(tms_path)' in template else False
        self.with_arcgiscache_path = True if '%(arcgiscache_path)' in template else False
        self.with_bbox = True if '%(bbox)' in template else False

    def substitute(self, tile_coord, format=None, grid=None):
        x, y, z = tile_coord
        data = dict(x=x, y=y, z=z)
        data['format'] = format or self.format
        if self.with_quadkey:
            data['quadkey'] = quadkey(tile_coord)
        if self.with_tc_path:
            data['tc_path'] = tilecache_path(tile_coord)
        if self.with_tms_path:
            data['tms_path'] = tms_path(tile_coord)
        if self.with_arcgiscache_path:
            data['arcgiscache_path'] = arcgiscache_path(tile_coord)
        if self.with_bbox:
            data['bbox'] = bbox(tile_coord, grid)

        return self.template % data
    
    def __repr__(self):
        return '%s(%r, format=%r)' % (
            self.__class__.__name__, self.template, self.format)

def tilecache_path(tile_coord):
    """
    >>> tilecache_path((1234567, 87654321, 9))
    '09/001/234/567/087/654/321'
    """
    x, y, z = tile_coord
    parts = ("%02d" % z,
             "%03d" % int(x / 1000000),
             "%03d" % (int(x / 1000) % 1000),
             "%03d" % (int(x) % 1000),
             "%03d" % int(y / 1000000),
             "%03d" % (int(y / 1000) % 1000),
             "%03d" % (int(y) % 1000))
    return '/'.join(parts)

def quadkey(tile_coord):
    """
    >>> quadkey((0, 0, 1))
    '0'
    >>> quadkey((1, 0, 1))
    '1'
    >>> quadkey((1, 2, 2))
    '21'
    """
    x, y, z = tile_coord
    quadKey = ""
    for i in range(z,0,-1):
        digit = 0
        mask = 1 << (i-1)
        if (x & mask) != 0:
            digit += 1
        if (y & mask) != 0:
            digit += 2
        quadKey += str(digit)
    return quadKey

def tms_path(tile_coord):
    """
    >>> tms_path((1234567, 87654321, 9))
    '9/1234567/87654321'
    """
    return '%d/%d/%d' % (tile_coord[2], tile_coord[0], tile_coord[1])

def arcgiscache_path(tile_coord):
   """
   >>> arcgiscache_path((1234567, 87654321, 9))
   'L09/R05397fb1/C0012d687'
   """
   return 'L%02d/R%08x/C%08x' % (tile_coord[2], tile_coord[1], tile_coord[0])

def bbox(tile_coord, grid):
    """
    >>> from mapproxy.grid import tile_grid
    >>> grid = tile_grid(4326, bbox=(0, -15, 10, -5))
    >>> bbox((0, 0, 0), grid)
    '0.00000000,-15.00000000,10.00000000,-5.00000000'
    >>> bbox((0, 0, 1), grid)
    '0.00000000,-15.00000000,5.00000000,-10.00000000'
    
    >>> grid = tile_grid(4326, bbox=(0, -15, 10, -5), origin='nw')
    >>> bbox((0, 0, 1), grid)
    '0.00000000,-10.00000000,5.00000000,-5.00000000'
    """
    return '%.8f,%.8f,%.8f,%.8f' % grid.tile_bbox(tile_coord)

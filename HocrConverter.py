#!/usr/bin/env python3
"""HocrConverter

Convert Files from hOCR to pdf

Usage:
  HocrConverter.py [-tIcbmnrV] [-q | -v | -vv] [-i <inputHocrFile>] [-f <inputTtfFile>] (-o <outputPdfFile>) [<inputImageFile>]...
  HocrConverter.py (-h | --help)

Options:
  -h --help             Show this screen.
  -t                    Make ocr-text visible
  -i <inputHocrFile>    hOCR input file
  -o <outputPdfFile>    pdf output
  -f <inputTtfFile>     use custom TTF font
  -I                    include images
  -c                    use full line text
  -b                    draw bounding boxes around ocr-text
  -n                    don't read images supplied in hocr-file
  -m                    do multiple pages in hocr and output pdf
  -r                    take hOCR-image sizes as reference for size of page
  -V                    vertical Inversion ( for ocropus: false, for tesseract: true )
  -q | -v | -vv         quiet ( only warnings and errors ) | verbose | very verbose = debug

"""

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
#from reportlab.lib.units import cm as inch
from reportlab.lib.units import pica
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.etree.ElementTree import ElementTree
import PIL.Image
import re
import sys
import logging
import unicodedata
try:
  from docopt import docopt
except ImportError:
  exit('This scrip requires that python `docopt` command line parsing library'
       ' is installed: \n pip install docopt\n'
       'https://github.com/docopt/docopt')
try:
  from schema import Schema, And, Or, Use, SchemaError, Optional
except ImportError:
  exit('This script requires that python `schema` data-validation library'
       ' is installed: \n pip install schema\n'
       'https://github.com/halst/schema')

class HocrConverter():
  """
  A class for converting documents to/from the hOCR format.
  
  For details of the hOCR format, see:
  
    http://docs.google.com/View?docid=dfxcv4vc_67g844kf
    
  See also:
  
    http://code.google.com/p/hocr-tools/
  
  Basic usage:
  
  Create a PDF from an hOCR file and an image:
    
    hocr = HocrConverter("path/to/hOCR/file")
    hocr.to_pdf("path/to/image/file", "path/to/output/file")
  
  """
  import reportlab.rl_config
  reportlab.rl_config.warnOnMissingFontGlyphs = 0

  def __init__(self, hocrFileName = None):
    self.hocr = None
    self.xmlns = ''
    self.boxPattern = re.compile('bbox((\s+\d+){4})')
    # self.filenamePattern = re.compile('file\s+(.*)')  
    self.filenamePattern = re.compile(".*(file|image)\s((?:\"|')(?:[^'\"]+)(?:['\"])|(?:[^\s'\"]+)).*")
    if hocrFileName is not None:
      self.parse_hocr(hocrFileName)
      
  def __str__(self):
    """
    Return the textual content of the HTML body
    """
    if self.hocr is None:
      return ''
    body =  self.hocr.find(".//%sbody"%(self.xmlns))
    if body:
      return self._get_element_text(body).encode('utf-8') # XML gives unicode
    else:
      return ''
  
  def _get_element_text(self, element):
    """
    Return the textual content of the element and its children
    """
    text = ''
    if element.text is not None:
      text = text + element.text
    for child in element.getchildren():
      text = text + self._get_element_text(child)
    if element.tail is not None:
      text = text + element.tail
    return text
  
  def parse_element_title(self, element):
    if 'title' in element.attrib:
      dict_return = {}
      
      vprint( VVERBOSE, element.attrib['title'] )
      matches = self.boxPattern.search(element.attrib['title'])
      if matches:
        coords = matches.group(1).split()
        out = (int(coords[0]),int(coords[1]),int(coords[2]),int(coords[3]))
        dict_return[ "bbox" ] = out
   
      matches = self.filenamePattern.search(element.attrib['title'])
      if matches:        
        dict_return[ "file" ] = matches.groups()[1].strip("\"'")
    
    return dict_return
    
  def element_coordinates(self, element):
    """
    Returns a tuple containing the coordinates of the bounding box around
    an element
    """
    text_coords = (0,0,0,0)
    parse_result = self.parse_element_title( element )
    if "bbox" in parse_result:
          text_coords = parse_result["bbox"]

    return text_coords
    
  def parse_hocr(self, hocrFileName):
    """
    Reads an XML/XHTML file into an ElementTree object
    """
    self.hocr = ElementTree()
    self.hocr.parse(hocrFileName)
    
    # if the hOCR file has a namespace, ElementTree requires its use to find elements
    matches = re.match('({.*})html', self.hocr.getroot().tag)
    if matches:
      self.xmlns = matches.group(1)
    else:
      self.xmlns = ''

  def _setup_image(self, imageFileName):
    
    vprint( INFO, "Image File:", imageFileName )
      
    im = PIL.Image.open(imageFileName)
    imwidthpx, imheightpx = im.size
    
    vprint( VERBOSE, "Image Dimensions:", im.size )
    
    if 'dpi' in im.info:
      width = float(im.size[0])/im.info['dpi'][0]
      height = float(im.size[1])/im.info['dpi'][1]
    else:
      # we have to make a reasonable guess
      # set to None for now and try again using info from hOCR file
      width = height = None
    
    return (im, width, height)

  def get_ocr_text_extension( self, page ):
    """
    Get the maximum extension of the area covered by text
    """
    if not self.hocr:
      vprint( VERBOSE, "No hOCR." )
      return None

    x_min = x_max = y_min = y_max = 0

    for line in page.findall(".//%sspan"%(self.xmlns)):
      if line.attrib['class'] == 'ocr_line':
        text_coords = self.element_coordinates(line)
      
        for coord_x in [ text_coords[0], text_coords[2] ]:
          if coord_x > x_max:
            x_max = coord_x
          if coord_x < x_min:
            x_min = coord_x
        for coord_y in [ text_coords[1], text_coords[3] ]:
          if coord_y > y_max:
            y_max = coord_y
          if coord_y < y_min:
            y_min = coord_y

    return (x_min,y_min,x_max,y_max)

  def getTextElements( self, parent_element ):
    text_element_types = [ "p", "span" ]
    
    text_elements = []
    for cat in text_element_types:
      cat_text_elements = parent_element.findall(".//%s%s"%(self.xmlns,cat))
      vprint( VVERBOSE, cat,":",len(cat_text_elements) )
      text_elements.extend( cat_text_elements )

    return text_elements

  def to_pdf(self, imageFileNames, outFileName, fontname="Helvetica", fontsize=12, withVisibleOCRText=False, withVisibleImage=True, withVisibleBoundingBoxes=False, noPictureFromHocr=False, multiplePages=False, hocrImageReference=False, verticalInversion=False ):
    """
    Creates a PDF file with an image superimposed on top of the text.
    
    Text is positioned according to the bounding box of the lines in
    the hOCR file.
    
    The image need not be identical to the image used to create the hOCR file.
    It can be scaled, have a lower resolution, different color mode, etc.
    """
   
    # create the PDF file 
    pdf = Canvas(outFileName, pageCompression=1)

    if self.hocr is None:
      # warn that no text will be embedded in the output PDF
      vprint( WARN, "Warning: No hOCR file specified. PDF will be image-only." )

    if inputFontFileName is not None:
      pdfmetrics.registerFont(TTFont('Custom', inputFontFileName))
      fontname = "Custom"
    
    # Collect pages from hOCR
    pages = []
    if self.hocr is not None:
      divs = self.hocr.findall(".//%sdiv"%(self.xmlns))
      for div in divs:
        if div.attrib['class'] == 'ocr_page':
          pages.append(div)

    vprint( VVERBOSE, len(pages), "pages;", len(imageFileNames), "image files from command line." ) 
    
    page_count = 0
    # loop pages
    while True:
      page_count += 1
      vprint( VERBOSE, "page", page_count )
      
      if len(pages) >= page_count:
        page = pages[page_count-1] 
      else:
        page = None

      if page_count > 1:
        if not multiplePages:
          vprint (INFO, "Only processing one page." )
          break # there shouldn't be more than one, and if there is, we don't want it
     
      imageFileName = None
      
      # Check for image from command line 
      if imageFileNames:
        # distinct file
        if len(imageFileNames) >= page_count:
          imageFileName = imageFileNames[page_count-1]
        # repeat the last file
        else:
          imageFileName = imageFileNames[-1]
          # stop if no more ocr date
          if page == None:
            break
      else:
        if page == None:
          break

      vprint ( VERBOSE, "Image file name:", imageFileName )
      
      vprint ( VERBOSE, "page:", page.tag, page.attrib )
      # Dimensions of ocr-page
      if page is not None:
        coords = self.element_coordinates( page )
      else:
        coords = (0,0,0,0)

      ocrwidth = coords[2]-coords[0]
      ocrheight = coords[3]-coords[1]
      
      # Load command line image
      if imageFileName:
        im, width, height = self._setup_image(imageFileName)
        vprint( VVERBOSE, "width, heigth:", width, height )
      else:
        im = width = height = None
        
      # Image from hOCR
      # get dimensions, which may not match the image
      im_ocr = None
      if page is not None:
        parse_result = self.parse_element_title( page )
        vprint( VVERBOSE, "ocr_page file ?" )
        vprint( VVERBOSE, "Parse Results:",parse_result )
        if "file" in parse_result:
          imageFileName_ocr_page = parse_result["file"] 
          vprint( VERBOSE, "ocr_page file", imageFileName_ocr_page, nolinebreak=True )
        
          if noPictureFromHocr:
            vprint( VERBOSE, "- ignored.", nolinebreak=True )
          if imageFileName:
            vprint( VERBOSE, "- ignored (overwritten by command line).", nolinebreak=True )

          vprint( VERBOSE, "" )

          if ( ( not noPictureFromHocr ) and ( not imageFileName) ) or hocrImageReference:
            im_ocr, width_ocr, height_ocr = self._setup_image(imageFileName_ocr_page)
            vprint( VERBOSE, "hOCR width, heigth:", width, height )
          if ( not noPictureFromHocr ) and ( not imageFileName):
            im = im_ocr
            width = width_ocr
            height = height_ocr

        # Get size of text area in hOCR-file
        ocr_text_x_min, ocr_text_y_min, ocr_text_x_max, ocr_text_y_max = self.get_ocr_text_extension( page )
        ocr_text_width = ocr_text_x_max
        ocr_text_height = ocr_text_y_max

        if not ocrwidth:
          if im_ocr:
            ocrwidth = im_ocr.size[0]
          else:
            ocrwidth = ocr_text_width 

        if not ocrheight:
          if im_ocr:
            ocrheight = im_ocr.size[1]
          else:
            ocrheight = ocr_text_height
     
        vprint( VERBOSE, "ocrwidth, ocrheight :", ocrwidth, ocrheight )
     
      if ( ( not ocrwidth ) and ( ( not width ) or ( not withVisibleImage ) ) ) or ( ( not ocrheight) and ( ( not height ) or ( not withVisibleImage ) ) ):
        vprint( WARN, "Page with extension 0 or without content. Skipping." )
      else:

        if page is not None:
          vprint( VERBOSE, "page not None")
          ocr_dpi = (300, 300) # a default, in case we can't find it
        
          if width is None:
            # no dpi info with the image
            # assume OCR was done at 300 dpi
            width = ocrwidth / 300.0
            height = ocrheight / 300.0
            vprint( VERBOSE, "Assuming width, height:",width,height )
        
          ocr_dpi = (ocrwidth/width, ocrheight/height)
          #ocr_dpi = (300, 300)
       
          vprint( VERBOSE, "ocr_dpi :", ocr_dpi )
        
        if width is None:
          # no dpi info with the image, and no help from the hOCR file either
          # this will probably end up looking awful, so issue a warning
          vprint( WARN, "Warning: DPI unavailable for image %s. Assuming 96 DPI."%(imageFileName) )
          width = float(im.size[0])/96
          height = float(im.size[1])/96
          
        # PDF page size
        pdf.setPageSize((width*inch, height*inch)) # page size in points (1/72 in.)
        
        # put the image on the page, scaled to fill the page
        if withVisibleImage:
          if im:
            pdf.drawInlineImage(im, 0, 0, width=width*inch, height=height*inch)
          else:
            vprint( INFO, "No inline image file supplied." )
       
        # put ocr-content on the page 
        if self.hocr is not None:
          text_elements = self.getTextElements( page )
          
          for line in text_elements:
            import pdb
            vprint( VVERBOSE, line.tag, line.attrib )
            if 'class' in line.attrib:
              text_class = line.attrib['class']
            else:
              text_class = None
            if text_class in [ 'ocr_line', 'ocrx_word', 'ocr_carea', 'ocr_par' ]:
              
              if text_class == 'ocr_line':
                textColor = (0,0,0)
                bboxColor = (0,255,0)
              elif text_class == 'ocrx_word' :
                textColor = (0,0,0)
                bboxColor = (0,255,255)
              elif text_class == 'ocr_carea' :
                textColor = (255,0,0)
                bboxColor = (255,255,0)
              elif text_class == 'ocr_par' :
                textColor = (255,0,0)
                bboxColor = (255,0,0)
              
              coords = self.element_coordinates( line )
              parse_result = self.parse_element_title( line )
              
              text = pdf.beginText()
              text.setFont(fontname, fontsize)
              
              text_corner1x = (float(coords[0])/ocr_dpi[0])*inch
              text_corner1y = (float(coords[1])/ocr_dpi[1])*inch

              text_corner2x = (float(coords[2])/ocr_dpi[0])*inch
              text_corner2y = (float(coords[3])/ocr_dpi[1])*inch
              
              text_width = text_corner2x - text_corner1x
              text_height = text_corner2y - text_corner1y
              
              if verticalInversion:
                text_corner2y_inv = (height*inch) - text_corner1y
                text_corner1y_inv = (height*inch) - text_corner2y
                
                text_corner1y = text_corner1y_inv
                text_corner2y = text_corner2y_inv

              # set cursor to bottom left corner of line bbox (adjust for dpi)
              text.setTextOrigin( text_corner1x, text_corner1y )
           
              # The content of the text to write
              if withFullLineText:
                textContent = unicodedata.normalize("NFC",unicode(" ".join([elem for elem in map((lambda text: text.strip()),line.itertext()) if len(elem) > 0])))
              else:
                textContent = line.text
                if ( textContent == None):
                # Text in tag can be embeded in other tags. In that case
                # we need to search recursively in all tags
                # We search recursively only in tags <span> which
                # contain only non tag span like <strong> or <em>
                  span_child = 0
                  for child_tag in line.iter("%sspan"%(self.xmlns)):
                    span_child = span_child + 1
                # The line.tag contain no other <span> tag.
                # It can contains some text. We search recursively
                # in all tags contained in this <span> tag
                  if span_child == 1:
                    for string_text in line.itertext():
                      if string_text != None:
                         textContent = string_text
                         break
                if ( textContent == None ):
                  textContent = u""
                textContent = textContent.rstrip()
              
              # scale the width of the text to fill the width of the line's bbox
              if len(textContent) != 0:
                text.setHorizScale( ((( float(coords[2])/ocr_dpi[0]*inch ) - ( float(coords[0])/ocr_dpi[0]*inch )) / pdf.stringWidth( textContent, fontname, fontsize))*100)

              if not withVisibleOCRText:
                text.setTextRenderMode(3) # invisible
             
              # Text color
              text.setFillColorRGB(textColor[0],textColor[1],textColor[2])

              # write the text to the page
              text.textLine( textContent )

              vprint( VVERBOSE, "processing", text_class, coords,"->", text_corner1x, text_corner1y, text_corner2x, text_corner2y, ":", textContent )
              pdf.drawText(text)

              pdf.setLineWidth(0.1)
              pdf.setStrokeColorRGB(bboxColor[0],bboxColor[1],bboxColor[2])
       
              # Draw a box around the text object
              if withVisibleBoundingBoxes: 
                pdf.rect( text_corner1x, text_corner1y, text_width, text_height);
     
        # finish up the page. A blank new one is initialized as well.
        pdf.showPage()
    
    # save the pdf file
    vprint( INFO, "Writing pdf." )
    pdf.save()
  
  def to_text(self, outFileName):
    """
    Writes the textual content of the hOCR body to a file.
    """
    f = open(outFileName, "w")
    f.write(self.__str__())
    f.close()

def setGlobal( varName ):
  def setValue( value ):
    vprint( VVERBOSE, varName, "=", value )
    globals()[varName] = value;
    return True
  return setValue

def appendGlobal( varName ):
  def appendValue( value ):
    globals()[varName].append( value )
    vprint( VVERBOSE, varName, "=", globals()[varName] )
    return True
  return appendValue

VVERBOSE = 5            # Custom level
VERBOSE = logging.DEBUG # 10
INFO = logging.INFO     # 20
WARN = logging.WARN     # 30
ERROR = logging.ERROR   # 40

_vprint_text = ""

def vprint( verbosity, *data, **keywords ):
  """
  logs/prints depending on verbosity level
  
  verbosity levels:
    VVERBOSE = 5 ( -vv )
    VERBOSE = 10 ( -v )
    INFO = 20
    WARN = 30    ( -q )
    ERROR = 40
  """
  
  if "nolinebreak" in keywords:
    nolinebreak = keywords["nolinebreak"]
  else:
    nolinebreak = False

  global _vprint_text

  out_text = _vprint_text
  for out in data:
    if out_text != "":
      out_text += " "
    out_text += str(out)

  # If nolinebreak is enabled, save message for next output
  if nolinebreak:
    if logging.root.isEnabledFor( verbosity ):
      _vprint_text = out_text
  else:
    _vprint_text = ""
    logging.log( verbosity, out_text )

def setLogThreshold( cmd_threshold ):
  
  if type( cmd_threshold ) == bool :
    if cmd_threshold == True:     # -q
      threshold = WARN
    elif cmd_threshold == False:  # no -q argument
      return True
  
  elif type( cmd_threshold ) == int :
    if cmd_threshold == 0:        # no -v argument
      threshold = INFO
    elif cmd_threshold == 1:      # -v
      threshold = VERBOSE
    elif cmd_threshold == 2:      # -vv
      threshold = VVERBOSE

  logging.root.setLevel( level = threshold )
  vprint(VVERBOSE, "loglevel:", threshold, "=", logging.getLevelName( threshold) )
  return True

if __name__ == "__main__":
  # Variables to control program function
  withVisibleOCRText = False;
  withVisibleImage = True;
  withFullLineText = False;
  withVisibleBoundingBoxes = False;
  noPictureFromHocr = False
  multiplePages = False
  inputImageFileNames = []
  inputImageFileName = None
  inputHocrFileName = None
  inputFontFileName = None
  hocrImageReference = False
  verticalInversion=False
  logThreshold=logging.INFO

  # Init output/logging
  logging.addLevelName("VVERBOSE",5)
  logging.basicConfig(format='%(message)s', level=logging.NOTSET)

  # Taking care of command line arguments
  arguments = docopt(__doc__)
  
  # Validation of arguments and setting of global variables
  # As a first pass check for verbosity settings
  schema_verbosity = Schema({
        '-v': setLogThreshold,
        '-q': setLogThreshold,
        str: object })

  # Second run for all the other options
  schema = Schema({
        '-i': And( setGlobal( "inputHocrFileName" ), lambda n: Use(open, error="Can't open <inputHocrFile>") if n else True ) ,
        '-f': And( setGlobal( "inputFontFileName" ), lambda n: Use(open, error="Can't open <inputFontFileName>") if n else True ),
        '--help': bool,
        '-I': setGlobal( "withVisibleImage" ),
        '-c': setGlobal( "withFullLineText" ),
        '-b': setGlobal( "withVisibleBoundingBoxes" ),
        '-m': setGlobal( "multiplePages" ),
        '-n': setGlobal( "noPictureFromHocr" ),
        '-t': setGlobal( "withVisibleOCRText" ),
        '-r': setGlobal( "hocrImageReference" ),
        '-V': setGlobal( "verticalInversion" ),
        '-v': object,
        '-q': object,
        '<inputImageFile>': [ And( appendGlobal( "inputImageFileNames" ), Use(open, error="Can't open <inputImageFile>") ) ],
        '-o': setGlobal( "outputPdfFileName" ) })
  try:
    args = schema_verbosity.validate( arguments )
    args = schema.validate( arguments )
  except SchemaError as e:
    vprint( ERROR, "Error:" )
    vprint( ERROR, " ", e )
    vprint( ERROR, "Error Details:" )
    vprint( ERROR, " ", e.autos )
    exit(1) 

  vprint(VVERBOSE, arguments)
  
  hocr = HocrConverter( inputHocrFileName )
  hocr.to_pdf( inputImageFileNames, outputPdfFileName, withVisibleOCRText=withVisibleOCRText, withVisibleImage=withVisibleImage, withVisibleBoundingBoxes=withVisibleBoundingBoxes, noPictureFromHocr=noPictureFromHocr, multiplePages=multiplePages, hocrImageReference=hocrImageReference, verticalInversion=verticalInversion )

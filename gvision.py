# © 2020 James R Barlow: https://github.com/jbarlow83
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
An example of an OCRmyPDF plugin.
This plugin adds two new command line arguments
    --grayscale-ocr: converts the image to grayscale before performing OCR on it
        (This is occasionally useful for images whose color confounds OCR. It only
        affects the image shown to OCR. The image is not saved.)
    --mono-page: converts pages all pages in the output file to black and white
To use this from the command line:
    ocrmypdf --plugin path/to/example_plugin.py --mono-page input.pdf output.pdf
To use this as an API:
    import ocrmypdf
    ocrmypdf.ocr('input.pdf', 'output.pdf',
        plugins=['path/to/example_plugin.py'], mono_page=True
    )


    $ pip3 freeze | grep google-cloud-vision
google-cloud-vision==2.0.0
If you're using a local development environment or using a new virtual environment you just created, install/update the client library (including pip itself if necessary) with this command:


$ pip3 install -U pip google-cloud-vision
...
Successfully installed google-cloud-vision-2.0.0
Confirm the client library can be imported without issue like the below, and then you're ready to use the Vision API from real code!


$ python3 -c "import google.cloud.vision"

python file from https://github.com/dinosauria123/gcv2hocr/blob/master/gcv2hocr2.py

copy files
apt-get update
apt-get install python3-distutils
pip3 install google-cloud-vision
--plugin gvision.py
"""

import logging
import pathlib

from ocrmypdf import hookimpl
from ocrmypdf import hocrtransform
from ocrmypdf._exec import tesseract
from ocrmypdf.pluginspec import OcrEngine

import io
import os
import sys
from google.cloud import vision
from google.cloud.vision_v1 import AnnotateImageResponse
import json

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
import gcv2hocr2

log = logging.getLogger(__name__)


@hookimpl
def add_options(parser):
    # Just to add the option for the apikey, maybe as a config in future?
    parser.add_argument('--apikey', default='./cloudkey.json', action='store')


@hookimpl
def prepare(options):
    print(options)
    pass


@hookimpl
def validate(pdfinfo, options):
    log.debug("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    log.debug(options)
    if not options.apikey:
        log.error("there is no api key given")
        raise ocrmypdf.ExitCodeException("there is no api key given")
    pass


''''@hookimpl
def filter_page_image(page, image_filename):
    if page.options.mono_page:
        with Image.open(image_filename) as im:
            im = im.convert('1')
            im.save(image_filename)
        return image_filename
    else:
        output = image_filename.with_suffix('.jpg')
        with Image.open(image_filename) as im:
            im.save(output)
        return output
'''


class GVisionOcrEngine(OcrEngine):

    @staticmethod
    def creator_tag(options):
        return "Google Vision as OCR"

    @staticmethod
    def version():
        return tesseract.version()

    def __str__(self):
        return "Try to use Google Vision Engine in MyOCRPDF"

    @staticmethod
    def generate_hocr(input_file, output_hocr, output_text, options):
        #print('HOCRHOCRCHOCOAODSOASDOOS')
        #initialize client
        client = vision.ImageAnnotatorClient.from_service_account_json(os.path.normpath(file_dir+'/'+options.apikey))

        #load file
        with io.open(input_file, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = client.document_text_detection(image=image, image_context={"language_hints": ["de"]})

        #get json response
        #https://newbedev.com/convert-google-vision-api-response-to-json
        json_response = AnnotateImageResponse.to_json(response)

        #modify response to feed it to gcv2hocr2
        resp_for_gcv = {"responses": [json.loads(json_response)]}

        '''with (open('json_response', 'w', encoding="utf-8")) as outfile:
            outfile.write(json_response)
            outfile.close()
        '''
        page = gcv2hocr2.fromResponse(resp_for_gcv, 'pagename')

        #output hocr
        with (open(output_hocr, 'w', encoding="utf-8")) as outfile:
            outfile.write(page.render().encode('utf-8') if str == bytes else page.render())
            outfile.close()

        with (open(output_text, 'w', encoding="utf-8")) as outfile:
            outfile.write(resp_for_gcv['responses'][0]['textAnnotations'][0]['description'])
            outfile.close()

    @staticmethod
    def generate_pdf(input_file, output_pdf, output_text, options):
        #print(output_pdf)
        hocr_tempfile = 'tempfile'
        GVisionOcrEngine.generate_hocr(input_file, hocr_tempfile, output_text, options)
        helper = hocrtransform.HocrTransform(
            hocr_filename = hocr_tempfile,
            dpi=300
        )

        helper.to_pdf(out_filename=output_pdf)
        helper.to_pdf(out_filename='output1.pdf',show_bounding_boxes=True)
        #helper.to_pdf(out_filename='output11.pdf', invisible_text=False, fontname='DarkGardenMK')
        #helper.to_pdf(out_filename='output111_pdf.pdf',image_filename=input_file, invisible_text=False, fontname='CALLIG15')
        #helper.to_pdf(out_filename='output11_pdf.pdf', image_filename=input_file, invisible_text=False,show_bounding_boxes=True)
        #helper.to_pdf(out_filename='output1_pdf.pdf', invisible_text=True,fontname='CALLIG15')
        #helper.to_pdf(out_filename=output_pdf, invisible_text=True, fontname='CALLIG15')
        #print('PDF END END END END END------------------')
        #import shutil
        #shutil.copy('hocr.pdf' , output_pdf)
        #print(output_pdf.name)

    @staticmethod
    def languages(options):
        return tesseract.get_languages()

    @staticmethod
    def get_orientation(input_file, options):
        return tesseract.get_orientation(
            input_file,
            engine_mode=options.tesseract_oem,
            timeout=options.tesseract_timeout,
        )

    @staticmethod
    def get_deskew(input_file, options) -> float:
        return tesseract.get_deskew(
            input_file,
            languages=options.languages,
            engine_mode=options.tesseract_oem,
            timeout=options.tesseract_timeout,
        )

    @staticmethod
    def languages(options):
        return {'deu','eng'}

@hookimpl
def get_ocr_engine():
    return GVisionOcrEngine()

#client = language.LanguageServiceClient.from_service_account_json("ocr-project-324713-d4819c87f883.json")

#gcv2hocr.py test.jpg.json > output.hocr


#type(response)
#serialized = MessageToJson(response)
#print(serialized)
# Performs label detection on the image file
#response = client.label_detection(image=image)


#labels = response.label_annotations

#print('Labels:')
#for label in labels:
#    print(label.description)


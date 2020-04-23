"""
This is the image data type used in the example files. The image type is selected
for simplicty and for minimal external dependencies; real applications are 
probably choosing different data types here.
"""
import ctypes as ct

# 25 Megapixel max
IMG_MAXSIZE = 25*1024*1024

class Image_ui8(ct.Structure):
    """
    An single channel 8 bit unsigned image.
    """
    _fields_ = [("width", ct.c_uint32),
                ("height", ct.c_uint32),
                ("data", ct.c_uint8*IMG_MAXSIZE)]


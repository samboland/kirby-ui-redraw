import unittest
from PIL import Image
from build_demos import resize_rgba

class ResampleTests(unittest.TestCase):
    def test_hidden_color_does_not_bleed(self):
        im=Image.new('RGBA',(2,1))
        im.putdata([(255,0,0,0),(0,0,255,255)])
        r,g,b,a=resize_rgba(im,(1,1)).getpixel((0,0))
        self.assertEqual((r,g,b),(0,0,255))
        self.assertTrue(126<=a<=129)

    def test_linear_light_average(self):
        im=Image.new('RGBA',(2,1))
        im.putdata([(0,0,0,255),(255,255,255,255)])
        r,g,b,a=resize_rgba(im,(1,1)).getpixel((0,0))
        self.assertTrue(186<=r<=189)
        self.assertEqual((r,r,255),(g,b,a))

if __name__=='__main__':unittest.main()

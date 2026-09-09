import struct
import unittest
from extract_textures import decode, decode_reference, decompress, archive_files, rgb565, rgb5a3, FORMATS, material_palettes
import random

class DecodeTests(unittest.TestCase):
    def test_material_palette_name_differs(self):
        data=bytearray(512)
        data[:4]=b'MDL0'
        struct.pack_into('>I',data,8,11)
        struct.pack_into('>I',data,0x30,64)
        struct.pack_into('>I',data,68,1)
        struct.pack_into('>I',data,100,64)
        struct.pack_into('>II',data,128+0x2c,1,64)
        struct.pack_into('>II',data,192,64,80)
        data[256:264]=b'texture\0'
        data[272:280]=b'palette\0'
        self.assertEqual(material_palettes(bytes(data)),{'texture':{'palette'}})

    def test_vectorized_matches_reference(self):
        rng=random.Random(8675309)
        for fmt,(bw,bh,bs,_) in FORMATS.items():
            with self.subTest(format=fmt):
                raw=rng.randbytes(bs*4)
                colors=[(i&255,(i*3)&255,(i*7)&255,(i*11)&255) for i in range(16384)]
                self.assertEqual(decode(raw,bw+1,bh+1,fmt,colors).tobytes(),
                                 decode_reference(raw,bw+1,bh+1,fmt,colors).tobytes())

    def test_lz11_overlap(self):
        # One literal A, followed by a five-byte overlapping copy.
        self.assertEqual(decompress(bytes.fromhex('1106000040414000')), b'AAAAAA')

    def test_lz10_overlap(self):
        self.assertEqual(decompress(bytes.fromhex('1006000040412000')), b'AAAAAA')

    def test_lz_bad_reference(self):
        with self.assertRaises(ValueError):
            decompress(bytes.fromhex('11030000802000'))

    def test_rgba_planes(self):
        raw=bytes([40,10]*16+[20,30]*16)
        image=decode(raw,4,4,6)
        self.assertEqual(image.getpixel((3,3)),(10,20,30,40))

    def test_ia8_byte_order(self):
        self.assertEqual(decode(bytes([40,180]*16),4,4,3).getpixel((0,0)),(180,180,180,40))

    def test_i4_alpha(self):
        self.assertEqual(decode(bytes([0xf0]*32),8,8,0).getpixel((0,0)),(255,)*4)
        self.assertEqual(decode(bytes([0xf0]*32),8,8,0).getpixel((1,0)),(0,)*4)

    def test_palette(self):
        colors=[(10,20,30,40),(50,60,70,80)]
        self.assertEqual(decode(bytes([0x10]*32),8,8,8,colors).getpixel((0,0)),colors[1])

    def test_block_order_and_crop(self):
        im=decode(bytes([255]*32+[0]*32),9,4,1)
        self.assertEqual(im.getpixel((7,3)),(255,)*4)
        self.assertEqual(im.getpixel((8,3)),(0,)*4)

    def test_cmpr_quadrants(self):
        red=bytes.fromhex('f800000000000000')
        green=bytes.fromhex('07e0000000000000')
        im=decode(red+green+green+red,8,8,14)
        self.assertEqual(im.getpixel((0,0)),(255,0,0,255))
        self.assertEqual(im.getpixel((7,0)),(0,255,0,255))
        self.assertEqual(im.getpixel((7,7)),(255,0,0,255))

    def test_cmpr_wii_blend(self):
        block=bytes.fromhex('f8000000aaaaaaaa')
        self.assertEqual(decode(block*4,8,8,14).getpixel((0,0)),(159,0,0,255))

    def test_lz11_long_forms(self):
        self.assertEqual(decompress(bytes.fromhex('111200004041000000')), b'A'*18)
        self.assertEqual(decompress(bytes.fromhex('11120100404110000000')), b'A'*274)

    def test_rgb5a3_alpha(self):
        self.assertEqual(rgb5a3(0x7fff),(255,)*4)
        self.assertEqual(rgb5a3(0x0fff),(255,255,255,0))

    def test_truncation(self):
        with self.assertRaises(ValueError):decode(b'',8,8,0)

    def test_u8(self):
        data=bytearray(100)
        struct.pack_into('>IIII',data,0,0x55aa382d,32,40,80)
        struct.pack_into('>III',data,32,0x01000000,0,2)
        struct.pack_into('>III',data,44,1,80,3)
        data[56:61]=b'\0tex\0';data[80:83]=b'abc'
        self.assertEqual(list(archive_files(bytes(data))),[('tex',b'abc')])

if __name__=='__main__':unittest.main()

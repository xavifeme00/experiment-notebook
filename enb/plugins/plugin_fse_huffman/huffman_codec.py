#!/usr/bin/env python3
"""Huffman codec wrapper
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2021/06/01"

import os
from enb import icompression


class Huffman(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self, huff_binary=os.path.join(os.path.dirname(os.path.abspath(__file__)), "fse")):
        icompression.WrapperCodec.__init__(self,
                                           compressor_path=huff_binary,
                                           decompressor_path=huff_binary,
                                           param_dict=None, output_invocation_dir=None)

        self.huff_binary = huff_binary

        assert os.path.isfile(huff_binary)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-h -f {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-h -d -f {compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return "Huffman"
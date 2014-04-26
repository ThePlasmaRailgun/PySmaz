#!/usr/bin/env python
# coding=utf-8
"""
PySmaz a Python port of the SMAZ short string text compression library.
Python port by Max Smith
Smaz by Salvatore Sanfilippo

BSD license per original C implementation at https://github.com/antirez/smaz

USAGE
-----

from lib.smaz import compress, decompress
compressedData = compress('Hello World!')
decompressedData = decompress(compressedData)

A FEW NOTES ON THE PYTHON PORT
------------------------------

PySmaz is Python 2.x, 3.x and PyPy compatible. I've tested with the latest versions, if you do find an issue with an
earlier version, please let me know, and address it.

The original C implementation used a table approach, along with some hashing to select the right entry. My first attempt
 used the original C-style approach and barely hit 170k/sec on Cython and a i7.

The tree based approach gets closer to one megabyte per second on the same setup. The difference is performance is
largely due to the inner loop not always checking 7 characters per character - i.e. O(7n) vs O(n). I've tried to balance
readability with performance, hopefully it's clear what's going on.

Decompression performance is limited by the single byte approach, and reaches 3.7 megabytes per second. To squeeze
more performance it might be worth considering a multi-byte table for decoding.

After eliminating the O(n^2) string appends, PyPy performance is much good:
   Compression throughput is 1.5 megabytes per second (1.5x)
   Decompression throughput is 22 megabytes per second (7x)

How should you use it ?

Well - there's the rub: In pure python form is probably too slow to be universally useful, until PyPy can get much
faster anyway. Interestingly smaz isn't too far off bz2... but zlib crushes it.

                    smaz (Cython) smaz(PyPy)         bz2          zlib
 Comp   throughput  1.0 mb/s       1.5 mb/s     2.0 mb/s    74.07 mb/s
 Decomp throughput  3.7 mb/s      22.0 mb/s   30.39 mb/s   454.55 mb/s

If you have a use-case where you need to keep an enormous amount of small strings that isn't going to be limited by
PySmaz's limited throughput, then congratulations !

The unit tests explore its performance against a series of common compressible strings. You'll notice it does very well
against bz2 and zlib on English text, URLs and paths. In the Moby Dick sample SMAZ is best out to 54 characters (see
unit test) and is often number one on larger samples out to hundreds of bytes. The first paragraph of Moby Dick as an
example, SMAZ leads until 914 bytes of text have passed !

On non-English strings (numbers, symbols, nonsense) it still does better with everything under 9 bytes (see unit test)
And ignoring big wins for zlib like repeating sub-strings, out to 20 bytes it is dominant. This is mostly thanks to the
pathological case detection in the compress routine.

POSSIBLE ENHANCEMENTS TO THE ALGORITHM
--------------------------------------
There are a few things left on the table as far as improving the compression of the algorithm, we can squeeze an extra
char into the '255' block, and despite being only for ascii text the uncompressed runs waste a bit per character.

If we assume that we only ever encode ASCII, then instead of encoding the length of the string in the second byte after
a 255, we could encode as much ASCII content as we like, followed by a 255, additionally the other 126 non-ascii values
could be used as a secondary dictionary values.

To increased relative domain effectiveness it might make sense to replace the single character 254 encoding with a
secondary dictionary lookup. Using this effectively would require greater encoding complexity and would thus be slower.

BACKGROUND
----------

From the original description:

    SMAZ - compression for very small strings
    -----------------------------------------

    Smaz is a simple compression library suitable for compressing very short
    strings. General purpose compression libraries will build the state needed
    for compressing data dynamically, in order to be able to compress every kind
    of data. This is a very good idea, but not for a specific problem: compressing
    small strings will not work.

    Smaz instead is not good for compressing general purpose data, but can compress
    text by 40-50% in the average case (works better with English), and is able to
    perform a bit of compression for HTML and urls as well. The important point is
    that Smaz is able to compress even strings of two or three bytes!

    For example the string "the" is compressed into a single byte.

    To compare this with other libraries, think that like zlib will usually not be able to compress text shorter than
    100 bytes.

    COMPRESSION EXAMPLES
    --------------------

    'This is a small string' compressed by 50%
    'foobar' compressed by 34%
    'the end' compressed by 58%
    'not-a-g00d-Exampl333' enlarged by 15%
    'Smaz is a simple compression library' compressed by 39%
    'Nothing is more difficult, and therefore more precious, than to be able to decide' compressed by 49%
    'this is an example of what works very well with smaz' compressed by 49%
    '1000 numbers 2000 will 10 20 30 compress very little' compressed by 10%

    In general, lowercase English will work very well. It will suck with a lot
    of numbers inside the strings. Other languages are compressed pretty well too,
    the following is Italian, not very similar to English but still compressible
    by smaz:

    'Nel mezzo del cammin di nostra vita, mi ritrovai in una selva oscura' compressed by 33%
    'Mi illumino di immenso' compressed by 37%
    'L'autore di questa libreria vive in Sicilia' compressed by 28%

    It can compress URLS pretty well:

    'http://google.com' compressed by 59%
    'http://programming.reddit.com' compressed by 52%
    'http://github.com/antirez/smaz/tree/master' compressed by 46%

    CREDITS
    -------
    Small was written by Salvatore Sanfilippo and is released under the BSD license. See __License__ section for more
    information
"""

__author__ = "Max Smith and Salvatore Sanfilippo"
__copyright__ = "Copyright 2006-2014 Max Smith, Salvatore Sanfilippo"
__credits__ = ["Max Smith", "Salvatore Sanfilippo"]
__license__ = """
BSD License
Copyright (c) 2006-2009, Salvatore Sanfilippo
Copyright (c) 2014, Max Smith
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this list of conditions and the
      following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
      following disclaimer in the documentation and/or other materials provided with the distribution.
    * Neither the name of Smaz nor the names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
__version__ = "1.0.0"
__maintainer__ = "Max Smith"
__email__ = None  # Sorry, I get far too much spam as it is. Track me down at http://www.notonbluray.com


def make_tree(decode_table):
    """ Create a tree representing the encoding strategy implied by the passed table.
        For each string in the table, assign it an encoded value, walk through the string
        creating a node for each character at a position (if none already exists), and when
        we reach the end of the string populate that node with the assigned encoded value.

    :param decode_table: list
    """
    root_node = {}
    if not decode_table:
        raise ValueError('Empty data passed to make_tree')
    elif len(decode_table) > 254:
        raise ValueError('Too long list in make tree: %d' % len(decode_table))
    else:
        for enc_byte, sstr in enumerate(decode_table):
            node_ptr = root_node
            for str_pos, ch in enumerate(sstr):
                if node_ptr.get(ch):  # If a child node exists for character
                    terminal_byte, children = node_ptr.get(ch)
                    if len(sstr) == str_pos + 1:  # At the end ?
                        if not terminal_byte:
                            node_ptr[ch] = (chr(enc_byte), children)
                            break
                        else:
                            raise ValueError(
                                'Unexpected terminal: duplicates in data (%s) (%s) (%s)' % (sstr, ch, node_ptr))
                    node_ptr = children
                else:  # Create the child node
                    if len(sstr) == str_pos + 1:  # At the end ?
                        node_ptr[ch] = (chr(enc_byte), {})
                    else:
                        node_ptr[ch] = (None, {})
                        _, node_ptr = node_ptr[ch]
    return root_node

# Can be up to 253 entries in this table.
DECODE = (" ", "the", "e", "t", "a", "of", "o", "and", "i", "n", "s", "e ", "r", " th",
          " t", "in", "he", "th", "h", "he ", "to", "\r\n", "l", "s ", "d", " a", "an",
          "er", "c", " o", "d ", "on", " of", "re", "of ", "t ", ", ", "is", "u", "at",
          "   ", "n ", "or", "which", "f", "m", "as", "it", "that", "\n", "was", "en",
          "  ", " w", "es", " an", " i", "\r", "f ", "g", "p", "nd", " s", "nd ", "ed ",
          "w", "ed", "http://", "for", "te", "ing", "y ", "The", " c", "ti", "r ", "his",
          "st", " in", "ar", "nt", ",", " to", "y", "ng", " h", "with", "le", "al", "to ",
          "b", "ou", "be", "were", " b", "se", "o ", "ent", "ha", "ng ", "their", "\"",
          "hi", "from", " f", "in ", "de", "ion", "me", "v", ".", "ve", "all", "re ",
          "ri", "ro", "is ", "co", "f t", "are", "ea", ". ", "her", " m", "er ", " p",
          "es ", "by", "they", "di", "ra", "ic", "not", "s, ", "d t", "at ", "ce", "la",
          "h ", "ne", "as ", "tio", "on ", "n t", "io", "we", " a ", "om", ", a", "s o",
          "ur", "li", "ll", "ch", "had", "this", "e t", "g ", "e\r\n", " wh", "ere",
          " co", "e o", "a ", "us", " d", "ss", "\n\r\n", "\r\n\r", "=\"", " be", " e",
          "s a", "ma", "one", "t t", "or ", "but", "el", "so", "l ", "e s", "s,", "no",
          "ter", " wa", "iv", "ho", "e a", " r", "hat", "s t", "ns", "ch ", "wh", "tr",
          "ut", "/", "have", "ly ", "ta", " ha", " on", "tha", "-", " l", "ati", "en ",
          "pe", " re", "there", "ass", "si", " fo", "wa", "ec", "our", "who", "its", "z",
          "fo", "rs", ">", "ot", "un", "<", "im", "th ", "nc", "ate", "><", "ver", "ad",
          " we", "ly", "ee", " n", "id", " cl", "ac", "il", "</", "rt", " wi", "div",
          "e, ", " it", "whi", " ma", "ge", "x", "e c", "men", ".com")

# Can be regenerated with the below line
# SMAZ_TREE = make_tree(DECODE)
SMAZ_TREE = {'\n': ('1', {'\r': (None, {'\n': ('\xa7', {})})}), '\r': ('9', {'\n': ('\x15', {'\r': ('\xa8', {})})}),
             ' ': ('\x00', {'a': ('\x19', {' ': ('\x92', {}), 'n': ('7', {})}), ' ': ('4', {' ': ('(', {})}),
                            'c': ('I', {'l': ('\xee', {}), 'o': ('\xa1', {})}), 'b': ('^', {'e': ('\xaa', {})}),
                            'e': ('\xab', {}),
                            'd': ('\xa5', {}), 'f': ('h', {'o': ('\xd5', {})}),
                            'i': ('8', {'t': ('\xf6', {}), 'n': ('N', {})}),
                            'h': ('U', {'a': ('\xc9', {})}), 'm': ('{', {'a': ('\xf8', {})}), 'l': ('\xcd', {}),
                            'o': ('\x1d',
                                  {'n': ('\xca', {}), 'f': (' ', {})}), 'n': ('\xec', {}), 'p': ('}', {}),
                            's': ('>', {}), 'r': ('\xbd',
                                                  {'e': ('\xd1', {})}),
                            't': ('\x0e', {'h': ('\r', {}), 'o': ('R', {})}), 'w': ('5', {'a': ('\xb9', {}),
                                                                                          'h': ('\x9f', {}),
                                                                                          'e': ('\xe9', {}),
                                                                                          'i': ('\xf3', {})})}),
             '"': ('e', {}), '-': ('\xcc', {}), ',':
    ('Q', {' ': ('$', {'a': ('\x94', {})})}), '/': ('\xc5', {}), '.': ('n', {' ': ('y', {}), 'c': (None,
                                                                                                   {'o': (None, {'m': (
                                                                                                   '\xfd', {})})})}),
             '=': (None, {'"': ('\xa9', {})}), '<': ('\xe1', {'/': ('\xf1',
                                                                    {})}), '>': ('\xde', {'<': ('\xe6', {})}),
             'T': (None, {'h': (None, {'e': ('H', {})})}),
             'a': ('\x04', {' ': ('\xa3', {}), 'c': ('\xef', {}), 'd': ('\xe8', {}), 'l': ('X', {'l': ('p', {})}),
                            'n': ('\x1a', {'d': ('\x07', {})}), 's': ('.', {' ': ('\x8c', {}), 's': ('\xd3', {})}),
                            'r': ('O', {'e': ('w', {})}),
                            't': ("'", {'i': ('\xce', {}), ' ': ('\x87', {}), 'e': ('\xe5', {})})}),
             'c': ('\x1c', {'h': ('\x99', {' ': ('\xc1', {})}), 'e': ('\x88', {}), 'o': ('u', {})}),
             'b': ('Z', {'y': ('\x7f', {}), 'u': (None, {'t': ('\xb1', {})}), 'e': ('\\', {})}),
             'e': ('\x02', {'a': ('x', {}), ' ': ('\x0b', {'a': ('\xbc', {}), 'c': ('\xfb', {}),
                                                           's': ('\xb5', {}), 't': ('\x9c', {}), 'o': ('\xa2', {})}),
                            'c': ('\xd7', {}), 'e': ('\xeb', {}),
                            'd': ('B', {' ': ('@', {})}), '\r': (None, {'\n': ('\x9e', {})}), 'l': ('\xb2', {}),
                            'n': ('3',
                                  {' ': ('\xcf', {}), 't': ('a', {})}), 's': ('6', {' ': ('~', {})}),
                            'r': ('\x1b', {' ': ('|', {}),
                                           'e': ('\xa0', {})}), ',': (None, {' ': ('\xf5', {})})}),
             'd': ('\x18', {'i': ('\x81',
                                  {'v': ('\xf4', {})}), ' ': ('\x1e', {'t': ('\x86', {})}), 'e': ('j', {})}),
             'g': (';', {' ':
                             ('\x9d', {}), 'e': ('\xf9', {})}),
             'f': (',', {' ': (':', {'t': ('v', {})}), 'r': (None, {'o': (None,
                                                                          {'m': ('g', {})})}),
                         'o': ('\xdc', {'r': ('D', {})})}), 'i': ('\x08', {'c': ('\x83', {}), 'd': ('\xed',
                                                                                                    {}),
                                                                           'm': ('\xe2', {}), 'l': ('\xf0', {}),
                                                                           'o': ('\x90', {'n': ('k', {})}),
                                                                           'n': ('\x0f', {' ': ('i',
                                                                                                {}), 'g': ('F', {})}),
                                                                           's': ('%', {' ': ('t', {})}),
                                                                           't': ('/', {'s': ('\xda', {})}),
                                                                           'v': ('\xba',
                                                                                 {})}),
             'h': ('\x12', {'a': ('b', {'v': (None, {'e': ('\xc6', {})}), 'd': ('\x9a', {}), 't': ('\xbe',
                                                                                                   {})}),
                            ' ': ('\x8a', {}), 'e': ('\x10', {' ': ('\x13', {}), 'r': ('z', {})}), 'i': ('f',
                                                                                                         {'s': (
                                                                                                         'L', {})}),
                            'o': ('\xbb', {}), 't': (None, {'t': (None, {'p': (None, {':': (None, {'/': (None,
                                                                                                         {'/': ('C',
                                                                                                                {})})})})})})}),
             'm': ('-', {'a': ('\xad', {}), 'e': ('l', {'n': ('\xfc', {})})}),
             'l': ('\x16', {'a': ('\x89', {}), ' ': ('\xb4', {}), 'e': ('W', {}), 'i': ('\x97', {}), 'l': ('\x98', {}),
                            'y': ('\xea', {' ': ('\xc7', {})})}),
             'o': ('\x06', {' ': ('`', {}), 'f': ('\x05', {' ': ('"', {})}),
                            'm': ('\x93', {}), 'n': ('\x1f', {' ': ('\x8e', {}), 'e': ('\xae', {})}),
                            'r': ('*', {' ': ('\xb0', {})}),
                            'u': ('[', {'r': ('\xd8', {})}), 't': ('\xdf', {})}),
             'n': ('\t', {' ': (')', {'t': ('\x8f', {})}), 'c':
                 ('\xe4', {}), 'e': ('\x8b', {}), 'd': ('=', {' ': ('?', {})}), 'g': ('T', {' ': ('c', {})}), 'o':
                              ('\xb7', {'t': ('\x84', {})}), 's': ('\xc0', {}), 't': ('P', {})}),
             'p': ('<', {'e': ('\xd0', {})}), 's':
    ('\n', {' ': ('\x17', {'a': ('\xac', {}), 't': ('\xbf', {}), 'o': ('\x95', {})}), 'e': ('_', {}), 'i':
        ('\xd4', {}), ',': ('\xb6', {' ': ('\x85', {})}), 'o': ('\xb3', {}), 's': ('\xa6', {}), 't': ('M', {})}),
             'r': ('\x0c', {'a': ('\x82', {}), ' ': ('K', {}), 'e': ('!', {' ': ('q', {})}), 'i': ('r', {}), 'o': ('s',
                                                                                                                   {}),
                            's': ('\xdd', {}), 't': ('\xf2', {})}),
             'u': ('&', {'s': ('\xa4', {}), 'r': ('\x96', {}), 't': ('\xc4',
                                                                     {}), 'n': ('\xe0', {})}),
             't': ('\x03', {'a': ('\xc8', {}), ' ': ('#', {'t': ('\xaf', {})}), 'e': ('E',
                                                                                      {'r': ('\xb8', {})}),
                            'i': ('J', {'o': ('\x8d', {})}), 'h': ('\x11', {'a': ('\xcb', {'t': ('0', {})}),
                                                                            'i': (None, {'s': ('\x9b', {})}), 'e': (
             '\x01', {'i': (None, {'r': ('d', {})}), 'y': ('\x80', {}), 'r':
                 (None, {'e': ('\xd2', {})})}), ' ': ('\xe3', {})}), 'o': ('\x14', {' ': ('Y', {})}),
                            'r': ('\xc3', {})}),
             'w': ('A', {'a': ('\xd6', {'s': ('2', {})}), 'h': ('\xc2', {'i': ('\xf7', {'c': (None, {'h': ('+', {})})}),
                                                                         'o': ('\xd9', {})}),
                         'e': ('\x91', {'r': (None, {'e': (']', {})})}), 'i': (None, {'t': (None, {'h':
                                                                                                       ('V', {})})})}),
             'v': ('m', {'e': ('o', {'r': ('\xe7', {})})}), 'y': ('S', {' ': ('G', {})}), 'x':
    ('\xfa', {}), 'z': ('\xdb', {})}


def _check_ascii(sstr):
    """ Return True iff the passed string contains only ascii chars """
    return all(ord(ch) < 128 for ch in sstr)


def _encapsulate(input_str):
    """ There are some pathological cases, where it may be better to just encapsulate the string in 255 code chunks
    """
    if not input_str:
        return input_str
    else:
        output = []
        for chunk in (input_str[i:i + 255] for i in range(0, len(input_str), 255)):
            if 1 == len(chunk):
                output.append(chr(254) + chunk)
            else:
                output.append(chr(255) + chr(len(chunk) - 1))
                output.append(chunk)
        return "".join(output)


def compress(input_str, check_ascii=True, raise_on_error=True, compression_tree=None):
    """ Compress the passed string using the SMAZ algorithm. Returns the encoded string. Performance is a O(N), but the
        constant will vary depending on the relationship between the compression tree and input_str, in particular the
        average depth explored/average characters per encoded symbol.

    :param input_str The ASCII str to be compressed
    :param check_ascii Check the input_str is ASCII before we encode it (default True)
    :param raise_on_error Throw a value type exception (default True)
    :param compression_tree: A tree represented as a dict of ascii->char to tuple( encoded_byte, dict( ... ) ), that
                             describes how to compress content. By default uses built in SMAZ tree. See also make_tree
    :type input_str: str
    :type check_ascii: bool
    :type raise_on_error: bool
    :type compression_tree: dict

    :rtype: str
    :return: The compressed input_str
    """
    if not input_str:
        return input_str
    else:
        if check_ascii and not _check_ascii(input_str):
            if raise_on_error:
                raise ValueError('SMAZ can only process ASCII text.')
            else:
                return None

        terminal_tree_node = (None, None)
        compression_tree = compression_tree or SMAZ_TREE

        input_str_len = len(input_str)

        output = []
        unmatched = []
        pos = 0
        while pos < input_str_len:
            tree_ptr = compression_tree
            enc_byte = None
            enc_len = 0
            j = 0
            while j < input_str_len - pos:
                byte_val, tree_ptr = tree_ptr.get(input_str[pos + j], terminal_tree_node)
                j += 1
                if byte_val is not None:
                    enc_byte = byte_val
                    enc_len = j
                if not tree_ptr:
                    break  # No more matching characters in the tree

            if enc_byte is None:
                unmatched.append(input_str[pos])
                pos += 1  # We didn't match any stems, add the character the unmatched list
            else:
                pos += enc_len  # We did match, advance along, by the number of bytes encoded

            # Flush any unmatched if we are at the end of the string, buffer is full or, we just encoded a byte
            if unmatched and (input_str_len - pos == 0 or len(unmatched) == 255 or enc_byte is not None):
                if 1 == len(unmatched):
                    output.append(chr(254) + unmatched[0])
                else:
                    output.append(chr(255) + chr(len(unmatched) - 1))
                    output.extend(unmatched)
                unmatched = []

            if enc_byte:
                output.append(enc_byte)  # Emit the code we found in the tree

        # This may look a bit clunky, but it is worth 20% in cPython and O(n^2) -> O(n) in PyPy
        output = "".join(output)

        # Pathological case detection
        if len(output) > len(input_str) * 1.00390625:  # Did we grow more than we would by encapsulating the string ?
            return _encapsulate(input_str)

        return output


def decompress(input_str, raise_on_error=True, strict_checking=False, decompress_table=None):
    """ Returns decoded text from the input_str using the SMAZ algorithm by default
    :type input_str: str
    :type raise_on_error: bool
    :type strict_checking: bool
    :type decompress_table: list
    """
    if not input_str:
        return input_str
    else:
        decompress_table = decompress_table or DECODE
        input_str_len = len(input_str)
        output = []
        pos = 0
        try:
            while pos < input_str_len:
                ch = ord(input_str[pos])
                pos += 1
                if ch < 254:
                    # Code table entry
                    output.append(decompress_table[ch])
                else:
                    next_byte = input_str[pos]
                    pos += 1
                    if 254 == ch:
                        # Verbatim byte
                        output.append(next_byte)
                    else:  # 255 == ch:
                        # Verbatim string
                        len_str = ord(next_byte) + 1
                        end_pos = pos + len_str
                        if strict_checking and end_pos > input_str_len:
                            raise ValueError('Invalid input to SMAZ decompress - buffer overflow')
                        output.append(input_str[pos:end_pos])
                        pos = end_pos
            # This may look a bit clunky, but it is worth 20% in cPython and O(n^2)->O(n) in PyPy
            output = "".join(output)
            if strict_checking and not _check_ascii(output):
                raise ValueError('Invalid input to SMAZ decompress - non-ascii byte payload')
        except (IndexError, ValueError) as e:
            if raise_on_error:
                raise ValueError(str(e))
            else:
                return None
        return output
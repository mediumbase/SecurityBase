#!/usr/bin/env python
from setuptools import setup
from setuptools.extension import Extension
import numpy as np
import os

# Check if Cython is available
try:
    from Cython.Build import cythonize
    source_ext = '.pyx'
    use_cython = True
except ImportError:
    source_ext = '.c'
    use_cython = False

# Define the extension module
ext_modules = [
    Extension(
        "freenect",
        ["freenect" + source_ext],
        libraries=['usb-1.0', 'freenect', 'freenect_sync'],
        library_dirs=['/usr/local/lib', '/usr/local/lib64', '/usr/lib'],
        include_dirs=[
            '../../include',
            '/usr/include/libusb-1.0',
            '/usr/local/include/libusb-1.0',
            '/usr/local/include',
            '../c_sync',
            np.get_include()
        ],
        extra_compile_args=['-fPIC'],
    )
]

# Cythonize the extension if Cython is available
if use_cython:
    ext_modules = cythonize(ext_modules, language_level="3")

# Setup configuration
setup(
    name='freenect',
    ext_modules=ext_modules,
)
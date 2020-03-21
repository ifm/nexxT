#!/usr/bin/env python

# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import glob
import os
import sys
import platform
import sysconfig
import setuptools
import subprocess
from setuptools.command.build_ext import build_ext
from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES

# create platform specific wheel
try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel
    
    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            super().finalize_options()
            self.root_is_pure = False
            
        def get_tag(self):
            python, abi, plat = _bdist_wheel.get_tag(self)
            # uncomment for non-python extensions
            #python, abi = 'py3', 'none'
            return python, abi, plat
except ImportError:
    bdist_wheel = None
    
if platform.system() == "Linux":
    p = "linux_x86_64"
    presuf = [("lib", ".so")]
else:
    p = "msvc_x86_64"
    presuf = [("", ".dll"), ("", ".exp"), ("", ".lib")]
    

cv = sysconfig.get_config_vars()
cnexT = cv.get("EXT_PREFIX", "") + "cnexxT" + cv.get("EXT_SUFFIX", "")

build_files = []
for variant in ["nonopt", "release"]:
    build_files.append('nexxT/binary/' + p + '/' + variant + "/" + cnexT)
    for prefix,suffix in presuf:
        build_files.append('nexxT/binary/' + p + '/' + variant + "/" + prefix + "nexxT" + suffix)

# generate MANIFEST.in to add build files and include files
with open("MANIFEST.in", "w") as manifest:
    for fn in glob.glob('nexxT/include/*.hpp'):
        manifest.write("include " + fn + "\n")
    for bf in build_files:
        manifest.write("include " + bf + "\n")
    # json schema
    manifest.write("include nexxT/core/ConfigFileSchema.json")

setup(name='nexxT',
      install_requires=["PySide2 >=5.14.0, <5.15", "shiboken2 >=5.14.0, <5.15", "jsonschema>=3.2.0"], 
      version='0.0.0',
      description='nexxT extensible framework',
      author='pca',
      include_package_data = True,
      packages=['nexxT', 'nexxT.interface', 'nexxT.tests', 'nexxT.services', 'nexxT.services.gui', 'nexxT.tests.interface', 'nexxT.core', 'nexxT.tests.core'],
      cmdclass={
        'bdist_wheel': bdist_wheel,
      },
      entry_points = {
        'console_scripts' : ['nexxT-gui=nexxT.core.AppConsole:mainGui',
                             'nexxT-console=nexxT.core.AppConsole:mainConsole',
                            ]
      },
     )

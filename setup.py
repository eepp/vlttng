#!/usr/bin/env python
#
# The MIT License (MIT)
#
# Copyright (c) 2016 Philippe Proulx <eepp.ca>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import sys
from setuptools import setup


# make sure we run Python 3+ here
v = sys.version_info

if v.major < 3:
    sys.stderr.write('Sorry, vlttng needs Python 3\n')
    sys.exit(1)


import vlttng


setup(name='vlttng',
      version=vlttng.__version__,
      description='Generator of LTTng virtual environment',
      author='Philippe Proulx',
      author_email='eeppeliteloop@gmail.com',
      url='https://github.com/eepp/vlttng',
      packages=['vlttng'],
      package_data={
          'vlttng': ['profiles/*.yml'],
      },
      install_requires=['pyyaml', 'termcolor', 'setuptools'],
      entry_points={
          'console_scripts': [
              'vlttng = vlttng.vlttng_cli:run',
              'vlttng-quick = vlttng.vlttng_quick_cli:run',
          ]
      },
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: MIT License',
          'Natural Language :: English',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Software Development :: Build Tools',
      ])

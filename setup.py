#!/usr/bin/env python

"""GBS setup."""

import os, sys
import re

from distutils.core import setup

MOD_NAME = 'gitbuildsys'

def check_debian():
    """--install-layout is recognized after 2.5"""
    if sys.version_info[:2] > (2, 5):
        if len(sys.argv) > 1 and 'install' in sys.argv:
            try:
                import platform
                (dist, _, _) = platform.linux_distribution()
                # for debian-like distros, mods will be installed to
                # ${PYTHONLIB}/dist-packages
                if dist in ('debian', 'Ubuntu'):
                    sys.argv.append('--install-layout=deb')
            except AttributeError:
                pass

def get_version(mod_name):
    """Get version from module __init__.py"""
    path = os.path.join(mod_name, "__init__.py")
    if not os.path.isfile(path):
        print 'No %s version file found' % path
        sys.exit(1)

    content = open(path).read()
    match = re.search(r'^__version__\s*=\s*[\x22\x27]([^\x22\x27]+)[\x22\x27]',
                      content, re.M)
    if match:
        return match.group(1)

    print 'Unable to find version in %s' % path
    sys.exit(1)

check_debian()

setup(name='gbs',
      version=get_version(MOD_NAME),
      description='The command line tools for Tizen package developers',
      author='Jian-feng Ding, Huaxu Wan',
      author_email='jian-feng.ding@intel.com, huaxu.wan@intel.com',
      url='https://git.tizen.org/',
      scripts=['tools/gbs'],
      data_files=[('/etc/bash_completion.d/', ['data/gbs.sh']),
          ('/etc/zsh_completion.d/', ['data/_gbs'])],
      packages=[MOD_NAME],
)

#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# COPYRIGHT (c) 2016 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (c) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (c) 2006-2008 eL_vErDe <gandalf@le-vert.net>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Nicotine+ Launcher.
"""

import os
import platform
import sys
from pynicotine.logfacility import log
from pynicotine.utils import ApplyTranslation

# Setting gettext and locale
#ApplyTranslation()

# Detect if we're running on Windows
#win32 = platform.system().startswith("Win")

def version():
    try:
        import pynicotine.utils
        print ("Nicotine+ version %s" % pynicotine.utils.version)
    except ImportError, error:
        print ("Cannot find the pynicotine.utils module.")


def usage():
    print _("""Nicotine+ is a Soulseek client.
Usage: nicotine [OPTION]...
  -c file, --config=file      Use non-default configuration file
  -p dir,  --plugins=dir      Use non-default directory for plugins
  -t,      --enable-trayicon  Enable the tray icon
  -d,      --disable-trayicon Disable the tray icon
  -r,      --enable-rgba      Enable RGBA mode, for full program transparency
  -x,      --disable-rgba     Disable RGBA mode, default mode
  -h,      --help             Show help and exit
  -s,      --hidden           Start the program hidden so only the tray icon is shown
  -b ip,   --bindip=ip        Bind sockets to the given IP (useful for VPN)
  -v,      --version          Display version and exit""")


def renameprocess(newname, debug=False):

    errors = []

    # Renaming ourselves for ps et al.
    try:
        import procname
        procname.setprocname(newname)
    except:
        errors.append("Failed procname module")

    # Renaming ourselves for pkill et al.
    try:
        import ctypes
        # GNU/Linux style
        libc = ctypes.CDLL('libc.so.6')
        libc.prctl(15, newname, 0, 0, 0)
    except:
        errors.append("Failed GNU/Linux style")

    try:
        import dl
        # FreeBSD style
        libc = dl.open('/lib/libc.so.6')
        libc.call('setproctitle', newname + '\0')
        renamed = True
    except:
        errors.append("Failed FreeBSD style")

    if debug and errors:
        msg = [_("Errors occured while trying to change process name:")]
        for i in errors:
            msg.append("%s" % (i,))
        log.addwarning('\n'.join(msg))


def run():

    renameprocess('nicotine')

    import getopt
    import os.path
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hc:p:tdvswb:",
                                   [
                                    "help",
                                    "config=",
                                    "plugins=",
                                    "profile",
                                    "enable-trayicon",
                                    "disable-trayicon",
                                    "enable-rgba",
                                    "disable-rgba",
                                    "version",
                                    "hidden",
                                    "disable-webbrowser",
                                    "bindip="
                                   ]
                                   )
    except getopt.GetoptError:
        # print help information and exit
        usage()
        sys.exit(2)

    # if win32:
    #     try:
    #         mydir = os.path.join(os.environ['APPDATA'], 'nicotine')
    #     except KeyError:
    #         mydir, x = os.path.split(sys.argv[0])
    #     config = os.path.join(mydir, "config", "config")
    #     plugins = os.path.join(mydir, "plugins")
    # else:
    config = os.path.join(os.path.expanduser("~"), '.nicotine', 'config')
    plugins = os.path.join(os.path.expanduser("~"), '.nicotine', 'plugins')

    #profile = 0

    bindip = None


    app = frame.MainApp(config,  bindip)
    app.MainLoop()
    # if profile:
    #     import hotshot
    #     logfile = os.path.expanduser(config) + ".profile"
    #     profiler = hotshot.Profile(logfile)
    #     log.add(("Starting using the profiler (saving log to %s)") % logfile)
    #     profiler.runcall(app.MainLoop)
    # else:
        #app.MainLoop()
    # else:
    #     print result

if __name__ == '__main__':
    try:
        run()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()

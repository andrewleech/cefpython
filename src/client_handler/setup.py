import os
import sys
import struct
import platform
from setuptools import setup

COMPILE_FLAGS = ['-flto', '-std=gnu++11', '-g', '-Wall',
                 '-fPIC', '-Werror']

LINK_FLAGS = ['-flto', '-Wl,-rpath,.']

if len(sys.argv) > 1 and "--fast" in sys.argv:
    sys.argv.remove("--fast")
    # Fast mode disables optimization flags
    FAST = True
    print("FAST mode On")
else:
    FAST = False
    # Fix "ImportError ... undefined symbol ..." caused by CEF's include/base/
    # headers by adding the -flto flag (Issue #230). Unfortunately -flto
    # prolongs compilation time significantly.
    # More on the other flags: https://stackoverflow.com/questions/6687630/
    COMPILE_FLAGS += ['-fdata-sections', '-ffunction-sections']
    LINK_FLAGS += ['-Wl,--gc-sections']


# Architecture and OS postfixes
ARCH32 = (8 * struct.calcsize('P') == 32)
ARCH64 = (8 * struct.calcsize('P') == 64)
OS_POSTFIX = ("win" if platform.system() == "Windows" else
              "linux" if platform.system() == "Linux" else
              "mac" if platform.system() == "Darwin" else "unknown")
OS_POSTFIX2 = "unknown"
if OS_POSTFIX == "win":
    OS_POSTFIX2 = "win32" if ARCH32 else "win64"
elif OS_POSTFIX == "mac":
    OS_POSTFIX2 = "mac32" if ARCH32 else "mac64"
elif OS_POSTFIX == "linux":
    OS_POSTFIX2 = "linux32" if ARCH32 else "linux64"

# Directories
CLIENT_HANDLER_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.abspath(os.path.join(CLIENT_HANDLER_DIR, ".."))

# Python version string: "27" or "32".
PYTHON_VERSION = str(sys.version_info.major) + str(sys.version_info.minor)


client_handler_src = [
    'client_handler.cpp', 'cookie_visitor.cpp', 'resource_handler.cpp',
    'web_request_client.cpp', 'string_visitor.cpp', 'request_context_handler.cpp',
    'task.cpp', 'x11.cpp', 'context_menu_handler.cpp', 'display_handler.cpp',
    'download_handler.cpp', 'focus_handler.cpp', 'js_dialog_handler.cpp',
    'keyboard_handler.cpp', 'lifespan_handler.cpp', 'load_handler.cpp',
    'render_handler.cpp', 'request_handler.cpp'
]

if OS_POSTFIX.startswith('mac'):
    client_handler_src.append('util_mac.mm')


setup(
    name='client_handler',
    libraries=[('client_handler', dict(
        sources=[os.path.join(CLIENT_HANDLER_DIR, src) for src in client_handler_src],
        include_dirs=[
            r'./../',
            r'./../common/',
            r'/usr/include/python2.7',
            r'/usr/include/gtk-2.0',
            r'/usr/include/gtk-unix-print-2.0',
            r'/usr/include/glib-2.0',
            r'/usr/include/cairo',
            r'/usr/include/pango-1.0',
            r'/usr/include/gdk-pixbuf-2.0',
            r'/usr/include/atk-1.0',
            r'/usr/lib/x86_64-linux-gnu/gtk-2.0/include',
            r'/usr/lib/x86_64-linux-gnu/gtk-unix-print-2.0',
            r'/usr/lib/x86_64-linux-gnu/glib-2.0/include',
            r'/usr/lib/i386-linux-gnu/gtk-2.0/include',
            r'/usr/lib/i386-linux-gnu/gtk-unix-print-2.0',
            r'/usr/lib/i386-linux-gnu/glib-2.0/include',
            r'/usr/lib64/gtk-2.0/include',
            r'/usr/lib64/gtk-unix-print-2.0',
            r'/usr/lib64/glib-2.0/include',
            r'/usr/lib/gtk-2.0/include',
            r'/usr/lib/gtk-2.0/gtk-unix-print-2.0',
            r'/usr/lib/glib-2.0/include',
        ],

        # library_dirs=library_dirs,

        # Static libraries only. Order is important, if library A depends on B,
        # then B must be included before A.
        # libraries=libs,

        extra_compile_args=COMPILE_FLAGS,
        extra_link_args=LINK_FLAGS,
    ))],
)

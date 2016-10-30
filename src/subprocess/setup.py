import os
import sys
import struct
import platform
import fileinput
import subprocess

from setuptools import setup
from ext_targets import build_ext, StaticLibrary, Executable

COMPILE_FLAGS = ['-flto', '-std=gnu++11', '-g', '-Wall',
                          '-Werror', '-DRENDERER_PROCESS', '-static']

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
SUBPROCESS_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.abspath(os.path.join(SUBPROCESS_DIR, ".."))
CEFPYTHON_DIR = os.path.abspath(os.path.join(SRC_DIR, ".."))
BUILD_DIR = os.path.abspath(os.path.join(CEFPYTHON_DIR, "build"))
CEFPYTHON_BINARY = os.path.abspath(os.path.join(BUILD_DIR,
                                                "cefpython_"+OS_POSTFIX2))

CEF_BINARY = os.environ.get('CEF_BINARY')
if not CEF_BINARY or not os.path.exists(CEF_BINARY):
    CEF_BINARY = os.path.abspath(os.path.join(BUILD_DIR, "cef_"+OS_POSTFIX2))


UPSTREAM_BUILD = (os.path.exists(os.path.join(CEF_BINARY, 'bin')) and
                  os.path.exists(os.path.join(CEF_BINARY, 'lib')))

# Python version string: "27" or "32".
PYTHON_VERSION = str(sys.version_info.major) + str(sys.version_info.minor)

libcefpython_src = [
    'cefpython_app.cpp',
    'v8function_handler.cpp',
    'v8utils.cpp',
    'javascript_callback.cpp',
    'main_message_loop/main_message_loop.cpp',
    'main_message_loop/main_message_loop_std.cpp',
    'main_message_loop/main_message_loop_external_pump.cpp'
]

subprocess_src = [
    'main.cpp'
]

libs = [
    'cefpython',
    'glib-2.0',
    'gtk-x11-2.0',
    'cef_dll_wrapper',
    'cef',
]

include_dirs = [
    SRC_DIR,
    os.path.join(SRC_DIR, 'common'),
    os.path.join(CEF_BINARY),
    os.path.join(CEF_BINARY, 'include'),
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
]

if UPSTREAM_BUILD:
    libs.append('cef_dll_wrapper')
    library_dirs=[
        '.',
        os.path.join(CEF_BINARY,'bin'),
        os.path.join(CEF_BINARY,'lib'),
    ]
else:
    library_dirs=[
        '.',
        os.path.join(CEF_BINARY,'Release'),
        os.path.join(CEF_BINARY,'build','libcef_dll_wrapper'),
    ]

    # Build libcef_wrapper

    # Remove dependency on cefclient and cefsimple, we don't need
    # them and the spotify minimal builds don't include them
    for line in fileinput.input(os.path.join(CEF_BINARY,'CMakeLists.txt'), inplace=True):
        comment = ''
        if line.strip() in ('add_subdirectory(cefclient)',
                            'add_subdirectory(cefsimple)'):
            comment = '# '
        print('%s%s' % (comment, line), end='')

    # Run cmake
    wrapper_dir = os.path.join(CEF_BINARY,'build')
    if not os.path.exists(wrapper_dir):
        os.makedirs(wrapper_dir)
    subprocess.call(['cmake','-G','Ninja','-DCMAKE_BUILD_TYPE=Release','..'], cwd=wrapper_dir)

    subprocess.call(['ninja','libcef_dll_wrapper'], cwd=wrapper_dir)


if OS_POSTFIX.startswith('linux'):
    libs.insert(0, 'gobject-2.0')
    subprocess_src.append('print_handler_gtk.cpp')
    libcefpython_src.extend(['print_handler_gtk.cpp',
                             'main_message_loop/main_message_loop_external_pump_linux.cpp'])

elif OS_POSTFIX.startswith('mac'):
    libcefpython_src.append('main_message_loop/main_message_loop_external_pump_mac.mm')


libcefpython = StaticLibrary(
    name='cefpython',
    sources=[os.path.join(SUBPROCESS_DIR, src) for src in libcefpython_src],
    include_dirs=include_dirs,
    extra_compile_args=COMPILE_FLAGS,
    extra_link_args=LINK_FLAGS,
)

subprocess_exec = Executable(
    name="subprocess",
    sources=[os.path.join(SUBPROCESS_DIR, src) for src in subprocess_src],
    language='c++',
    include_dirs=include_dirs,
    library_dirs=library_dirs,
    libraries=libs,
    extra_compile_args=COMPILE_FLAGS,
    extra_link_args=LINK_FLAGS,
)

setup(
    name='subprocess_%s' % PYTHON_VERSION,
    cmdclass={'build_ext': build_ext},
    ext_modules=[libcefpython, subprocess_exec],
    setup_requires = ['setuptools_bin_targets>=1.2']
)

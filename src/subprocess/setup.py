import os
import sys
import struct
import platform

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as _build_ext
from distutils import log
from distutils.errors import DistutilsSetupError
from distutils.dep_util import newer_group

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
CEF_BINARY = os.path.abspath(os.path.join(BUILD_DIR, "cef_"+OS_POSTFIX2))
CEFPYTHON_BINARY = os.path.abspath(os.path.join(BUILD_DIR,
                                                "cefpython_"+OS_POSTFIX2))

# Python version string: "27" or "32".
PYTHON_VERSION = str(sys.version_info.major) + str(sys.version_info.minor)

class build_ext(_build_ext):

    def build_extension(self, ext):
        sources = ext.sources
        if sources is None or not isinstance(sources, (list, tuple)):
            raise DistutilsSetupError(
                  "in 'ext_modules' option (extension '%s'), "
                  "'sources' must be present and must be "
                  "a list of source filenames" % ext.name)
        sources = list(sources)

        ext_path = ext.name
        depends = sources + ext.depends
        if not (self.force or newer_group(depends, ext_path, 'newer')):
            log.debug("skipping '%s' extension (up-to-date)", ext.name)
            return
        else:
            log.info("building '%s' extension", ext.name)

        # First, scan the sources for SWIG definition files (.i), run
        # SWIG on 'em to create .c files, and modify the sources list
        # accordingly.
        sources = self.swig_sources(sources, ext)

        # Next, compile the source code to object files.

        # XXX not honouring 'define_macros' or 'undef_macros' -- the
        # CCompiler API needs to change to accommodate this, and I
        # want to do one thing at a time!

        # Two possible sources for extra compiler arguments:
        #   - 'extra_compile_args' in Extension object
        #   - CFLAGS environment variable (not particularly
        #     elegant, but people seem to expect it and I
        #     guess it's useful)
        # The environment variable should take precedence, and
        # any sensible compiler will give precedence to later
        # command line args.  Hence we combine them in order:
        extra_args = ext.extra_compile_args or []

        macros = ext.define_macros[:]
        for undef in ext.undef_macros:
            macros.append((undef,))

        objects = self.compiler.compile(sources,
                                         output_dir=self.build_temp,
                                         macros=macros,
                                         include_dirs=ext.include_dirs,
                                         debug=self.debug,
                                         extra_postargs=extra_args,
                                         depends=ext.depends)

        # XXX outdated variable, kept here in case third-part code
        # needs it.
        self._built_objects = objects[:]

        # Now link the object files together into a "shared object" --
        # of course, first we have to figure out all the other things
        # that go into the mix.
        if ext.extra_objects:
            objects.extend(ext.extra_objects)
        extra_args = ext.extra_link_args or []

        # Detect target language, if not provided
        language = ext.language or self.compiler.detect_language(sources)

        self.compiler.link_executable(
            objects, ext_path,
            libraries=self.get_libraries(ext),
            library_dirs=ext.library_dirs,
            runtime_library_dirs=ext.runtime_library_dirs,
            extra_postargs=extra_args,
            debug=self.debug,
            target_lang=language)

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
    'main.cpp',
    # 'cefpython_app.cpp',
    # 'v8function_handler.cpp',
    # 'v8utils.cpp',
    'javascript_callback.cpp'
]

libs = [
    'glib-2.0',
    'gtk-x11-2.0',
    'cef',
    'cef_dll_wrapper'
]

if OS_POSTFIX.startswith('linux'):
    libs.insert(0, 'gobject-2.0')
    subprocess_src.append('print_handler_gtk.cpp')
    libcefpython_src.extend(['print_handler_gtk.cpp',
                             'main_message_loop/main_message_loop_external_pump_linux.cpp'])

elif OS_POSTFIX.startswith('mac'):
    libcefpython_src.append('main_message_loop/main_message_loop_external_pump_mac.mm')

ext_modules = [
    Extension(
        "subprocess",
        [os.path.join(SUBPROCESS_DIR, src) for src in
         (subprocess_src + libcefpython_src)],

    language='c++',
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

    library_dirs=[
        os.path.join(CEF_BINARY,'bin'),
        os.path.join(CEF_BINARY,'lib'),
    ],

    # Static libraries only. Order is important, if library A depends on B,
    # then B must be included before A.
    libraries=libs,

    extra_compile_args=COMPILE_FLAGS,
    extra_link_args=LINK_FLAGS,
)]

setup(
    name='subprocess_%s' % PYTHON_VERSION,
    cmdclass={'build_ext': build_ext},
    ext_modules=ext_modules
)

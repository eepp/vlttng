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

activate_template = '''# The MIT License (MIT)
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

# Source this file from your shell (`source activate`) to activate this
# LTTng virtual environment.

# Local options
_vlttng_has_modules={has_modules}
_vlttng_has_java={has_java}

# Path to the virtual environment
VLTTNG={venv_path}
export VLTTNG

# Set new $PATH
_VLTTNG_OLD_PATH="$PATH"
PATH="$VLTTNG/usr/bin:$PATH"
export PATH

# Set new $LD_LIBRARY_PATH
_VLTTNG_OLD_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
LD_LIBRARY_PATH="$VLTTNG/usr/lib:$LD_LIBRARY_PATH"
export LD_LIBRARY_PATH

# Set new $CPPFLAGS
_VLTTNG_OLD_CPPFLAGS="$CPPFLAGS"
CPPFLAGS="-I$VLTTNG/usr/include $CPPFLAGS"
export CPPFLAGS

# Set new $LDFLAGS
_VLTTNG_OLD_LDFLAGS="$LDFLAGS"
LDFLAGS="-L$VLTTNG/usr/lib $LDFLAGS"
export LDFLAGS

# Set new $MANPATH
_VLTTNG_OLD_MANPATH="$MANPATH"
MANPATH="$VLTTNG/usr/share/man:$MANPATH"
export MANPATH

# Set new $PKG_CONFIG_PATH
_VLTTNG_OLD_PKG_CONFIG_PATH="$PKG_CONFIG_PATH"
PKG_CONFIG_PATH="$VLTTNG/lib/pkgconfig:$PKG_CONFIG_PATH"
export PKG_CONFIG_PATH

# Set $VLTTNG_CLASSPATH
if [ $_vlttng_has_java = 1 ]; then
    VLTTNG_CLASSPATH="$VLTTNG/usr/share/java/liblttng-ust-agent.jar:$VLTTNG/usr/share/java/log4j.jar"
    export VLTTNG_CLASSPATH
fi

# Save old $PYTHONPATH
_VLTTNG_OLD_PYTHONPATH="$PYTHONPATH"

# Add Python site packages to $PYTHONPATH
while read _vlttng_python_root; do
    # Installed Python packages directory, if available
    _vlttng_python_packages="$(find "$_vlttng_python_root" -maxdepth 1 -iname '*-packages' -a -type d | head -n1)"

    if [ -n "$_vlttng_python_packages" ]; then
        # Set new $PYTHONPATH
        if [ -z "$PYTHONPATH" ]; then
            PYTHONPATH="$_vlttng_python_packages"
        else
            PYTHONPATH="$_vlttng_python_packages:$PYTHONPATH"
        fi

        export PYTHONPATH
    fi

    unset _vlttng_python_packages
done < <(find "$VLTTNG/usr/lib" -maxdepth 1 -iname 'python*' -a -type d)

unset _vlttng_python_root

# Set new $LTTNG_HOME
_VLTTNG_OLD_LTTNG_HOME="$LTTNG_HOME"
LTTNG_HOME="$VLTTNG/home"
export LTTNG_HOME

# Save old $MODPROBE_OPTIONS
_VLTTNG_OLD_MODPROBE_OPTIONS="$MODPROBE_OPTIONS"

if [ $_vlttng_has_modules = 1 ]; then
    if [ "$VLTTNG_NO_RMMOD" != 1 ]; then
        _vlttng_removed_all_modules=0

        # Try to remove all the LTTng kernel modules
        while [ $_vlttng_removed_all_modules -eq 0 ]; do
            _vlttng_one_module=0

            for _vlttng_module in $(cat /proc/modules | cut -d' ' -f1 | grep '^lttng'); do
                _vlttng_one_module=1
                sudo rmmod $_vlttng_module 2>/dev/null
            done

            if [ $_vlttng_one_module -eq 0 ]; then
                _vlttng_removed_all_modules=1
            fi
        done

        unset _vlttng_removed_all_modules
        unset _vlttng_one_module
        unset _vlttng_module
    fi

    export MODPROBE_OPTIONS="-d '$VLTTNG/usr'"
fi

# Set the environment variables of this virtual environment
{env}

# Save old $PS1
_VLTTNG_OLD_PS1="$PS1"

# Set new prompt
if [ "$VLTTNG_NO_PROMPT" != 1 ]; then
    PS1="[$(basename "$VLTTNG")] $PS1"
    export PS1
fi

# Rehash
if [ -n "${{BASH-}}" ] || [ -n "${{ZSH_VERSION-}}" ]; then
    hash -r 2>/dev/null
fi

unset _vlttng_has_modules
unset _vlttng_has_java

vlttng-deactivate() {{
    unset VLTTNG
    unset VLTTNG_CLASSPATH

    PATH="$_VLTTNG_OLD_PATH"
    unset _VLTTNG_OLD_PATH

    LD_LIBRARY_PATH="$_VLTTNG_OLD_LD_LIBRARY_PATH"
    unset _VLTTNG_OLD_LD_LIBRARY_PATH

    CPPFLAGS="$_VLTTNG_OLD_CPPFLAGS"
    unset _VLTTNG_OLD_CPPFLAGS

    LDFLAGS="$_VLTTNG_OLD_LDFLAGS"
    unset _VLTTNG_OLD_LDFLAGS

    MANPATH="$_VLTTNG_OLD_MANPATH"
    unset _VLTTNG_OLD_MANPATH

    PKG_CONFIG_PATH="$_VLTTNG_OLD_PKG_CONFIG_PATH"
    unset _VLTTNG_OLD_PKG_CONFIG_PATH

    PYTHONPATH="$_VLTTNG_OLD_PYTHONPATH"
    unset _VLTTNG_OLD_PYTHONPATH

    LTTNG_HOME="$_VLTTNG_OLD_LTTNG_HOME"
    unset _VLTTNG_OLD_LTTNG_HOME

    MODPROBE_OPTIONS="$_VLTTNG_OLD_MODPROBE_OPTIONS"
    unset _VLTTNG_OLD_MODPROBE_OPTIONS

    PS1="$_VLTTNG_OLD_PS1"
    unset _VLTTNG_OLD_PS1

{unenv}

    unset -f vlttng-deactivate
}}
'''

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

# Path to the virtual environment
VLTTNG={venv_path}
export VLTTNG

# Path to the source of LTTng-modules, if available
_vlttng_modules_src={lttng_modules_src_path}

# Set new $PATH
_VLTTNG_OLD_PATH="$PATH"
PATH="$VLTTNG/usr/bin:$PATH"
export PATH

# Set new $LD_LIBRARY_PATH
_VLTTNG_OLD_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
LD_LIBRARY_PATH="$VLTTNG/usr/lib:$LD_LIBRARY_PATH"
export LD_LIBRARY_PATH

# Set new $MANPATH
_VLTTNG_OLD_MANPATH="$MANPATH"
MANPATH="$VLTTNG/usr/share/man:$MANPATH"
export MANPATH

# Python root path in the "lib" directory, if available
_vlttng_python_root="$(find "$LTTNG_VIRTUAL_ENV/usr/lib" -iname 'python*' -a -type d | head -n1)"

if [ -n "$_vlttng_python_root" ]; then
    # Installed Python packages directory, if available
    _vlttng_python_packages="$(find "$_vlttng_python_root" -maxdepth 1 -iname '*-packages' -a -type d | head -n1)"

    if [ -n "$_vlttng_python_packages" ]; then
        # Set new $PYTHONPATH
        _VLTTNG_OLD_PYTHONPATH="$PYTHONPATH"
        PYTHONPATH="$_vlttng_python_packages:$PYTHONPATH"
        export PYTHONPATH
    fi
fi

# Unset local variables
unset _vlttng_python_root
unset _vlttng_python_packages

if [ -n "$_vlttng_modules_src" ]; then
    if [ "$VLTTNG_NO_RMMOD" != 1 ]; then
        # First, unload the probes
        for module in $(cat /proc/modules | cut -d' ' -f1 | grep '^lttng_probe'); do
            sudo rmmod $module 2>/dev/null
        done

        # Then unload the ring buffer modules
        for module in $(cat /proc/modules | cut -d' ' -f1 | grep '^lttng_ring_buffer'); do
            sudo rmmod $module 2>/dev/null
        done

        # Unload the tracer
        sudo rmmod lttng_tracer 2>/dev/null

        # Unload everything else not in use anymore
        for module in $(cat /proc/modules | cut -d' ' -f1 | grep '^lttng'); do
            sudo rmmod $module 2>/dev/null
        done
    fi

    if [ "$VLTTNG_NO_MODULES_INSTALL" != 1 ]; then
        # Install the kernel modules
        (cd "$_vlttng_modules_src" && sudo make modules_install && sudo depmod -a)
    fi
fi

# Unset local variable
unset _vlttng_modules_src

# Kill all instances of LTTng and Babeltrace
if [ "$VLTTNG_NO_KILL" != 1 ]; then
    sudo pkill -9 lttng
    sudo pkill -9 babeltrace
fi

# Set the environment variables of this virtual environment
{env}

# Set new prompt
if [ "$VLTTNG_NO_PROMPT" != 1 ]; then
    _VLTTNG_OLD_PS1="$PS1"
    PS1="[$(basename "$VLTTNG")] $PS1"
    export PS1
fi

# Rehash
if [ -n "${{BASH-}}" ] || [ -n "${{ZSH_VERSION-}}" ]; then
    hash -r 2>/dev/null
fi
'''

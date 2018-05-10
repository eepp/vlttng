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

from vlttng.utils import perror
import vlttng.profile
import pkg_resources
import vlttng.venv
import argparse
import platform
import os.path
import vlttng
import re
import os


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('-f', '--force', action='store_true',
                    help='force the virtual environment creation')
    ap.add_argument('--hide-export', action='store_true',
                    help='hide export lines')
    ap.add_argument('-i', '--ignore-project', metavar='PROJECT',
                    action='append',
                    help='ignore project PROJECT (may be repeated)')
    ap.add_argument('-j', '--jobs', nargs='?', const=None, metavar='JOBS',
                    action='store', type=int,
                    default=1, help='number of make jobs to run simultaneously')
    ap.add_argument('-l', '--list-default-profiles', action='store_true',
                    help='list default profile names and exit')
    ap.add_argument('-o', '--override', metavar='PROP',
                    action='append',
                    help='override property in the effective profile (may be repeated)')
    ap.add_argument('-p', '--profile', metavar='PROFILE', action='append',
                    help='profile name or path (may be repeated to patch)')
    ap.add_argument('-v', '--verbose', action='store_true',
                    help='verbose output')
    ap.add_argument('-V', '--version', action='version',
                    version='%(prog)s {}'.format(vlttng.__version__))
    ap.add_argument('path', metavar='PATH', action='store', nargs='*',
                    help='virtual environment path')

    # parse args
    args = ap.parse_args()

    if not args.list_default_profiles and len(args.path) != 1:
        perror('Exactly one virtual environment path must be provided')

    if len(args.path) > 0:
        args.path = args.path[0]

    if args.ignore_project is None:
        args.ignore_project = []

    if args.profile is None:
        args.profile = []

    if args.override is None:
        args.override = []

    return args


def _find_profile(profile_name):
    try:
        filename = os.path.join(vlttng._PROFILES_DIRNAME,
                                '{}.yml'.format(profile_name))
        filename = pkg_resources.resource_filename(__name__, filename)

        if not os.path.isfile(filename):
            filename = profile_name
    except:
        filename = profile_name

    if not os.path.isfile(filename):
        perror('Cannot find profile "{}"'.format(profile_name))

    return filename


def _create_overrides(override_args):
    overrides = []

    try:
        for arg in override_args:
            arg = arg.strip()

            # replace
            m = re.match(r'^([a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]+)*)=(.+)$', arg)

            if m:
                path = m.group(1).split('.')
                rep = m.group(2)
                op = vlttng.profile.Override.OP_REPLACE
                overrides.append(vlttng.profile.Override(path, op, rep))
                continue

            # append
            m = re.match(r'^([a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]+)*)\+=(.+)$', arg)

            if m:
                path = m.group(1).split('.')
                rep = m.group(2)
                op = vlttng.profile.Override.OP_APPEND
                overrides.append(vlttng.profile.Override(path, op, rep))
                continue

            # remove
            m = re.match(r'^!([a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]+)*)$', arg)

            if m:
                path = m.group(1).split('.')
                op = vlttng.profile.Override.OP_REMOVE
                overrides.append(vlttng.profile.Override(path, op, None))
                continue

            perror('Malformed override option: "{}"'.format(arg))
    except vlttng.profile.InvalidOverride as e:
        perror('In override option: "{}": {}'.format(arg, e))

    return overrides


def _create_profile(profile_names, ignored_projects, override_args, verbose):
    filenames = []

    try:
        overrides = _create_overrides(override_args)
    except Exception as e:
        perror('Cannot parse overrides: {}'.format(e))

    for profile_name in profile_names:
        filenames.append(_find_profile(profile_name))

    try:
        profile = vlttng.profile.from_yaml_files(filenames, ignored_projects,
                                                 overrides, verbose)
    except vlttng.profile.ParseError:
        perror('Malformed YAML profile')
    except vlttng.profile.UnknownSourceFormat as e:
        perror('Unknown source format: "{}"'.format(e.source))
    except vlttng.profile.InvalidProfile as e:
        perror('Invalid profile: {}'.format(e))
    except:
        perror('Cannot read one of the specified profiles')

    return profile


def _register_sigint():
    if platform.system() == 'Linux':
        def handler(signal, frame):
            perror('Cancelled by user: virtual environment is incomplete')

        import signal
        signal.signal(signal.SIGINT, handler)


def _list_default_profiles():
    dirname = pkg_resources.resource_filename(__name__,
                                              vlttng._PROFILES_DIRNAME)

    for filename in sorted(os.listdir(dirname)):
        if filename.endswith('.yml'):
            print(filename[:-4])


def run():
    _register_sigint()
    args = _parse_args()

    if args.list_default_profiles:
        _list_default_profiles()
        return 0

    profile = _create_profile(args.profile, args.ignore_project, args.override,
                              args.verbose)

    try:
        vlttng.venv.VEnvCreator(args.path, profile, args.force, args.verbose,
                                args.jobs, args.hide_export)
    except Exception as e:
        perror('Unexpected error: {}'.format(e))

    return 0

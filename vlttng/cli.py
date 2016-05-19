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

from pkg_resources import resource_filename
from vlttng.utils import perror
import vlttng.profile
import vlttng.venv
import argparse
import platform
import os.path
import vlttng


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', '--jobs', metavar='JOBS', action='store', type=int,
                    default=1, help='number of make jobs to run simultaneously')
    ap.add_argument('-i', '--ignore-project', metavar='PROJECT',
                    action='append',
                    help='ignore project PROJECT (may be repeated)')
    ap.add_argument('-p', '--profile', metavar='PROFILE', action='append',
                    required=True,
                    help='profile name or path (may be repeated to patch)')
    ap.add_argument('-v', '--verbose', action='store_true',
                    help='verbose output')
    ap.add_argument('-V', '--version', action='version',
                    version='%(prog)s {}'.format(vlttng.__version__))
    ap.add_argument('path', metavar='PATH', action='store',
                    help='virtual environment path')

    # parse args
    args = ap.parse_args()

    if args.ignore_project is None:
        args.ignore_project = []

    if args.profile is None:
        args.profile = []

    return args


def _find_profile(profile_name):
    try:
        filename = os.path.join('profiles', '{}.yml'.format(profile_name))
        filename = resource_filename(__name__, filename)

        if not os.path.isfile(filename):
            filename = profile_name
    except:
        filename = profile_name

    if not os.path.isfile(filename):
        perror('Cannot find profile "{}"'.format(profile_name))

    return filename


def _create_profile(profile_names, ignored_projects, verbose):
    filenames = []

    for profile_name in profile_names:
        filenames.append(_find_profile(profile_name))

    try:
        profile = vlttng.profile.from_yaml_files(filenames, ignored_projects,
                                                 verbose)
    except vlttng.profile.ParseError:
        perror('Malformed YAML profile')
    except vlttng.profile.UnknownSourceFormat as e:
        perror('Unknown source format: "{}"'.format(e.source))
    except vlttng.profile.InvalidProfile as e:
        perror('Invalid profile: "{}"'.format(e))
    except:
        perror('Cannot read one of the specified profiles')

    return profile


def _register_sigint():
    if platform.system() == 'Linux':
        def handler(signal, frame):
            perror('Cancelled by user: virtual environment is incomplete')

        import signal
        signal.signal(signal.SIGINT, handler)


def run():
    _register_sigint()
    args = _parse_args()
    profile = _create_profile(args.profile, args.ignore_project, args.verbose)

    try:
        vlttng.venv.VEnvCreator(args.path, profile, args.verbose, args.jobs)
    except Exception as e:
        import traceback
        traceback.print_exc()
        perror('Unexpected error: {}'.format(e))


    return 0

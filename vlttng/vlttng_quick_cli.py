# The MIT License (MIT)
#
# Copyright (c) 2016-2020 Philippe Proulx <eepp.ca>
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

from collections import namedtuple
from vlttng.utils import perror
from termcolor import colored
import importlib.resources
import argparse
import platform
import vlttng
import shlex
import enum
import os
import re


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('-V', '--version', action='version',
                    version='%(prog)s {}'.format(vlttng.__version__))

    # parse args
    args = ap.parse_args()

    return args


def _register_sigint():
    if platform.system() == 'Linux':
        def handler(signal, frame):
            perror('Cancelled by user')

        import signal
        signal.signal(signal.SIGINT, handler)


def _bold(s):
    return colored(s, attrs=['bold'])


def _cquestion(s):
    return colored(s, 'cyan', attrs=['bold'])


def _cchoice(s):
    return _bold(s)


def _cprompt(p):
    return colored(p, 'yellow', attrs=['bold'])


def _cerror(e):
    return colored(e, 'red', attrs=['bold'])


@enum.unique
class _WizardState(enum.Enum):
    ASK_PROJECTS = 1
    ASK_MASTER = 2
    ASK_VERSIONS = 3
    ASK_FEATURE = 4
    ASK_BT_PYTHON = 5
    ASK_BT2_PYTHON = 6
    ASK_LTTNG_TOOLS_PYTHON = 7
    ASK_LTTNG_UST_JUL_AGENT = 8
    ASK_LTTNG_UST_LOG4J1_AGENT = 9
    ASK_LTTNG_UST_LOG4J2_AGENT = 10
    ASK_LTTNG_UST_PYTHON_AGENT = 11
    ASK_PYTHON_INTERPRETER = 12
    ASK_PATH = 13
    END = 14


class _Wizard:
    def __init__(self):
        self._profiles = []
        self._projects = []
        self._projects_versions = {}
        self._python_interpreter = None
        self._path = None
        self._state_handlers = {
            _WizardState.ASK_PROJECTS: self._state_ask_projects,
            _WizardState.ASK_MASTER: self._state_ask_all_master,
            _WizardState.ASK_VERSIONS: self._state_ask_versions,
            _WizardState.ASK_FEATURE: self._state_ask_feature,
            _WizardState.ASK_BT_PYTHON: self._state_ask_bt_python,
            _WizardState.ASK_BT2_PYTHON: self._state_ask_bt2_python,
            _WizardState.ASK_LTTNG_TOOLS_PYTHON: self._state_ask_lttng_tools_python,
            _WizardState.ASK_LTTNG_UST_JUL_AGENT: self._state_ask_lttng_ust_jul_agent,
            _WizardState.ASK_LTTNG_UST_LOG4J1_AGENT: self._state_ask_lttng_ust_log4j1_agent,
            _WizardState.ASK_LTTNG_UST_LOG4J2_AGENT: self._state_ask_lttng_ust_log4j2_agent,
            _WizardState.ASK_LTTNG_UST_PYTHON_AGENT: self._state_ask_lttng_ust_python_agent,
            _WizardState.ASK_PYTHON_INTERPRETER: self._state_ask_python_interpreter,
            _WizardState.ASK_PATH: self._state_ask_path,
        }
        self._project_name_to_title = {
            'babeltrace': ('Babeltrace 1',),
            'babeltrace2': ('Babeltrace 2',),
            'elfutils': ('elfutils', 'optional dependency of Babeltrace (1 and 2)'),
            'glib': ('GLib', 'dependency of Babeltrace (1 and 2)'),
            'libxml2': ('libxml2', 'dependency of LTTng-tools'),
            'lttng-analyses': ('LTTng analyses',),
            'lttng-modules': ('LTTng-modules',),
            'lttng-scope': ('LTTng Scope',),
            'lttng-tools': ('LTTng-tools',),
            'lttng-ust': ('LTTng-UST',),
            'popt': ('popt', 'dependency of Babeltrace 1 and LTTng-tools'),
            'tracecompass': ('Trace Compass',),
            'urcu': ('Userspace RCU', 'dependency of LTTng-tools and LTTng-UST'),
        }
        self._project_name_to_versions = {
            'babeltrace': [],
            'babeltrace2': [],
            'elfutils': [],
            'glib': [],
            'libxml2': [],
            'lttng-analyses': [],
            'lttng-modules': [],
            'lttng-scope': [],
            'lttng-tools': [],
            'lttng-ust': [],
            'popt': [],
            'tracecompass': [],
            'urcu': [],
        }

        filenames = []

        for res in (importlib.resources.files() / vlttng._PROFILES_DIRNAME).iterdir():
            if res.is_file() and res.name.endswith('.yml'):
                filenames.append(res.name)

        for filename in sorted(filenames):
            profile = filename[:-4]

            if not re.match(r'^.+-\d+(\.\d+)*$', profile):
                continue

            for project_name in self._project_name_to_versions:
                if profile.startswith(project_name + '-'):
                    profile_suffix = profile[len(project_name) + 1:]
                    self._project_name_to_versions[project_name].append(profile_suffix)

    def _handle_state(self):
        self._state_handlers[self._state]()

    def _get_cmd_line_args(self):
        args = ['vlttng']

        for profile in self._profiles:
            args += ['-p', profile]


        if self._python_interpreter is not None:
            args += ['-o', 'build-env.PYTHON={}'.format(self._python_interpreter)]
            args += ['-o', 'build-env.PYTHON_CONFIG={}-config'.format(self._python_interpreter)]

        args.append(shlex.quote(self._path))

        return args

    def start(self):
        self._state = _WizardState.ASK_PROJECTS
        print('''Welcome to the vlttng quickstart!

This questionnaire will help you create a basic vlttng profile to build
the projects and features you need.
''')

        while self._state != _WizardState.END:
            self._handle_state()

        args = self._get_cmd_line_args()

        print(_bold('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -'))
        print()
        print('Your command line is:')
        print()
        print(_bold(' '.join(args)))
        print()
        print('Note: You can add the {} argument to use N make jobs.'.format(_bold('-jN')))
        print()
        print(_cquestion('Would you like to run this command line?'))
        print()

        if self._get_yes_no(True):
            print()
            print(_cquestion('How many make jobs would you like?'))
            print()

            import multiprocessing

            prompt_ext = ' [{}]'.format(multiprocessing.cpu_count())

            while True:
                answer = self._input(prompt_ext, '')
                print()

                if answer == '':
                    ianswer = multiprocessing.cpu_count()
                    break

                try:
                    ianswer = int(answer.strip())
                except:
                    continue

                if ianswer < 1:
                    continue

                break

            args.append('-j{}'.format(ianswer))

            import subprocess

            try:
                subprocess.run(args)
            except:
                pass

    def _state_ask_projects(self):
        print(_cquestion('Which projects would you like to build?'))
        print()
        choices = (
            self._get_project_title('babeltrace'),
            self._get_project_title('babeltrace2'),
            self._get_project_title('elfutils'),
            self._get_project_title('glib'),
            self._get_project_title('libxml2'),
            self._get_project_title('lttng-analyses'),
            self._get_project_title('lttng-modules'),
            self._get_project_title('lttng-scope'),
            self._get_project_title('lttng-tools'),
            self._get_project_title('lttng-ust'),
            self._get_project_title('popt'),
            self._get_project_title('tracecompass'),
            self._get_project_title('urcu'),
        )
        choice_projects = (
            'babeltrace',
            'babeltrace2',
            'elfutils',
            'glib',
            'libxml2',
            'lttng-analyses',
            'lttng-modules',
            'lttng-scope',
            'lttng-tools',
            'lttng-ust',
            'popt',
            'tracecompass',
            'urcu',
        )
        self._pchoices(choices)
        self._pmultiple_choices_info()
        choices = self._get_choices(len(choices))
        print()

        if choices == 'a':
            self._projects = [project for project in choice_projects]
        else:
            for choice in choices:
                self._projects.append(choice_projects[choice - 1])

        self._state = _WizardState.ASK_MASTER

    def _state_ask_all_master(self):
        print(_cquestion('Which projects would you like to be built from their Git master version?'))
        print()
        choices = []
        choice_projects = []

        for project in self._projects:
            if project not in ('babeltrace', 'elfutils', 'popt'):
                choices.append(self._get_project_title(project))
                choice_projects.append(project)

        if len(choice_projects) == 0:
            self._state = _WizardState.ASK_VERSIONS
            return

        self._pchoices(choices)
        self._pmultiple_choices_info(with_none=True)
        choices = self._get_choices(len(choices), True)
        print()

        if choices == 'a':
            self._projects_versions = {p: 'master' for p in choice_projects}
        else:
            for choice in choices:
                self._projects_versions[choice_projects[choice - 1]] = 'master'

        self._state = _WizardState.ASK_VERSIONS

    def _state_ask_versions(self):
        projects = []

        for project in self._projects:
            if project not in self._projects_versions:
                projects.append(project)

        for project in projects:
            title = self._get_project_title(project)
            question = 'Which version of {} do you want to build?'.format(title[0])
            print(_cquestion(question))
            print()
            choices = []
            versions = self._project_name_to_versions[project]

            for version in versions:
                choices.append((version,))

            self._pchoices(choices)
            print()
            choice = self._get_choice(len(choices))
            print()

            version = versions[choice - 1]
            self._projects_versions[project] = version

        for project, version in self._projects_versions.items():
            self._profiles.append('{}-{}'.format(project, version))

        self._state = _WizardState.ASK_FEATURE

    def _state_ask_feature(self):
        self._state = _WizardState.ASK_BT_PYTHON

    def _state_ask_bt_python(self):
        next_state = _WizardState.ASK_BT2_PYTHON

        if 'babeltrace' not in self._projects:
            self._state = next_state
            return

        if 'lttng-analyses' in self._projects:
            self._profiles.append('babeltrace-python')
            self._state = next_state
            return

        print(_cquestion('Would you like to build the Babeltrace 1 Python bindings?'))
        print()

        if self._get_yes_no(False):
            self._profiles.append('babeltrace-python')

        print()
        self._state = next_state

    def _state_ask_bt2_python(self):
        next_state = _WizardState.ASK_LTTNG_TOOLS_PYTHON

        if 'babeltrace2' not in self._projects:
            self._state = next_state
            return

        print(_cquestion('Would you like to build the Babeltrace 2 Python bindings?'))
        print()

        if self._get_yes_no(False):
            self._profiles.append('babeltrace2-python')

        print()
        self._state = next_state

    def _state_ask_lttng_tools_python(self):
        if 'lttng-tools' not in self._projects:
            self._state = _WizardState.ASK_LTTNG_UST_JUL_AGENT
            return

        print(_cquestion('Would you like to build the LTTng-tools Python bindings?'))
        print()

        if self._get_yes_no(False):
            self._profiles.append('lttng-tools-python')

        print()
        self._state = _WizardState.ASK_LTTNG_UST_JUL_AGENT

    def _state_ask_lttng_ust_jul_agent(self):
        if 'lttng-ust' not in self._projects:
            self._state = _WizardState.ASK_LTTNG_UST_LOG4J1_AGENT
            return

        print(_cquestion('Would you like to build the LTTng-UST java.util.logging agent?'))
        print()

        if self._get_yes_no(False):
            self._profiles.append('lttng-ust-jul-agent')

        print()
        self._state = _WizardState.ASK_LTTNG_UST_LOG4J1_AGENT

    def _state_ask_lttng_ust_log4j1_agent(self):
        if 'lttng-ust' not in self._projects:
            self._state = _WizardState.ASK_LTTNG_UST_LOG4J2_AGENT
            return

        print(_cquestion('Would you like to build the LTTng-UST log4j 1.x agent?'))
        print()

        if self._get_yes_no(False):
            self._profiles.append('lttng-ust-log4j-agent')

        print()
        self._state = _WizardState.ASK_LTTNG_UST_LOG4J2_AGENT

    def _state_ask_lttng_ust_log4j2_agent(self):
        if 'lttng-ust' not in self._projects:
            self._state = _WizardState.ASK_LTTNG_UST_PYTHON_AGENT
            return

        print(_cquestion('Would you like to build the LTTng-UST Log4j 2 agent?'))
        print()

        if self._get_yes_no(False):
            self._profiles.append('lttng-ust-log4j2-agent')

        print()
        self._state = _WizardState.ASK_LTTNG_UST_PYTHON_AGENT

    def _state_ask_lttng_ust_python_agent(self):
        if 'lttng-ust' not in self._projects:
            self._state = _WizardState.ASK_PYTHON_INTERPRETER
            return

        print(_cquestion('Would you like to build the LTTng-UST Python agent?'))
        print()

        if self._get_yes_no(False):
            self._profiles.append('lttng-ust-python-agent')

        print()
        self._state = _WizardState.ASK_PYTHON_INTERPRETER

    def _state_ask_python_interpreter(self):
        found_python = False

        for profile in self._profiles:
            if 'python' in profile:
                found_python = True
                break

        if not found_python:
            self._state = _WizardState.ASK_PATH
            return

        print(_cquestion("What's your preferred Python interpreter?"))
        print()
        choices = (
            ('Python 2',),
            ('Python 3',),
        )

        self._pchoices(choices)
        print()
        choice = self._get_choice(len(choices))
        print()

        if choice == 1:
            self._python_interpreter = 'python2'
        else:
            self._python_interpreter = 'python3'

        self._state = _WizardState.ASK_PATH

    def _state_ask_path(self):
        print(_cquestion('Where would you like to create the virtual environment?'))
        print()
        answer = self._input(' [virt-lttng]', suffix='')
        print()

        if answer == '':
            answer = 'virt-lttng'

        self._path = answer
        self._state = _WizardState.END

    def _get_project_title(self, name):
        return self._project_name_to_title[name]

    def _pmultiple_choices_info(self, with_none=False):
        print()
        print('Enter a space-delimited list of choices,', end='')

        if with_none:
            print(' {} to select all,'.format(_bold('a')))
            print('or {} to select none.'.format(_bold('n')))
        else:
            print(' or {} to select all.'.format(_bold('a')))

        print()

    def _pchoices(self, choices):
        index_len = len(str(len(choices)))

        for index, choice in enumerate(choices):
            sinfo = ''

            if len(choice) > 1:
                sinfo = ' ({})'.format(choice[1])

            sindex = str(index + 1) + '.'
            sindex = sindex.rjust(index_len + 1)
            print('{} {}{}'.format(sindex, _cchoice(choice[0]), sinfo))

    def _perror(self, error):
        print(_cerror(error))

    def _pinvalid_choices(self, resp=None, suffix='s'):
        print()

        if resp is None:
            print()
            self._perror('Invalid choice{}'.format(suffix))
        else:
            self._perror('Invalid choice{}: {}'.format(suffix, resp))

        print()

    def _raw_choice_to_int(self, raw_choice, choice_max):
        try:
            choice = int(raw_choice)
        except:
            return

        if choice < 1 or choice > choice_max:
            return

        return choice

    def _try_get_choices(self, choice_max, all_default):
        prompt_ext = ''

        if all_default:
            prompt_ext = ' ({} for none) [{}]'.format(_bold('n'), _bold('a'))

        resp = self._input(prompt_ext)

        if resp == '':
            if all_default:
                return 'a'

            self._pinvalid_choices()
            return

        if resp == 'n':
            return set()

        raw_choices = re.split(r'\s+', resp)
        choices = set()

        for raw_choice in raw_choices:
            if raw_choice == 'a':
                return 'a'

            choice = self._raw_choice_to_int(raw_choice, choice_max)

            if choice is None:
                self._pinvalid_choices(resp)
                return

            choices.add(choice)

        return sorted(list(choices))

    def _get_choices(self, choice_max, all_default=False):
        while True:
            choices = self._try_get_choices(choice_max, all_default)

            if choices is not None:
                return choices

    def _try_get_choice(self, choice_max):
        resp = self._input(suffix='')

        if resp == '':
            self._pinvalid_choices(None, '')
            return

        choice = self._raw_choice_to_int(resp, choice_max)

        if choice is None:
            self._pinvalid_choices(resp, '')
            return

        return choice

    def _get_choice(self, choice_max):
        while True:
            choice = self._try_get_choice(choice_max)

            if choice is not None:
                return choice

    def _get_yes_no(self, default):
        default_yn = 'y' if default else 'n'
        prompt_ext = ' [{}]'.format(default_yn)

        while True:
            resp = self._input(prompt_ext, '')

            if resp == '':
                return default
            elif resp == 'y':
                return True
            elif resp == 'n':
                return False

            self._pinvalid_choices(resp, '')

    def _input(self, prompt_ext='', suffix=None):
        prompt = '{}{} '.format(_cprompt('==>'), prompt_ext)

        while True:
            try:
                resp = input(prompt)
            except EOFError:
                self._pinvalid_choices(None, suffix)
                continue

            return resp.strip()


def run():
    _register_sigint()
    args = _parse_args()
    wiz = _Wizard()
    wiz.start()

    return 0

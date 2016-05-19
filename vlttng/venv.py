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

import re
import os
import sys
import copy
import shlex
import os.path
import functools
import subprocess
import vlttng.profile
from termcolor import colored
from vlttng.utils import perror
from pathlib import PurePosixPath


def _pcmd(cmd):
    print(colored(cmd, attrs=['bold']))


def _psetenv(key, val):
    setenv = 'export {}={}'.format(key.strip(), shlex.quote(str(val)))
    print(colored(setenv, 'grey', attrs=['bold']))


_first_info_done = False


def _comment(msg):
    return '# {}'.format(msg)


def _pinfo(msg):
    global _first_info_done

    if _first_info_done:
        print()
    else:
        _first_info_done = True

    print(colored(_comment(msg), 'blue', attrs=['bold']))


def _pwarn(msg):
    print(colored(_comment('Warning: {}'.format(msg)), 'yellow', attrs=['bold']))


def _patch_env(env, paths):
    cflags = env.get('CFLAGS', '')
    include_dir = os.path.join(paths.usr, 'include')
    cflags += ' -I{}'.format(shlex.quote(include_dir))
    env['CFLAGS'] = cflags
    ldflags = env.get('LDFLAGS', '')
    lib_dir = os.path.join(paths.usr, 'lib')
    ldflags += ' -L{}'.format(shlex.quote(lib_dir))
    env['LDFLAGS'] = ldflags
    ld_library_path = env.get('LD_LIBRARY_PATH', '')
    ld_library_path = '{}:{}'.format(lib_dir, ld_library_path)
    env['LD_LIBRARY_PATH'] = ld_library_path


def _get_full_env(env, paths):
    new_env = copy.deepcopy(os.environ)

    try:
        new_env.update(env)
    except:
        perror('Invalid environment in profile')

    _patch_env(new_env, paths)

    return new_env


class _Runner:
    def __init__(self, verbose, jobs, paths):
        self._verbose = verbose
        self._cwd = None
        self._env = None
        self._jobs = jobs
        self._paths = paths

    def run(self, cmd):
        _pcmd(cmd)
        stdio = None if self._verbose else subprocess.DEVNULL
        popen = subprocess.Popen(cmd, stdin=None, stdout=stdio, stderr=stdio,
                                 shell=True, cwd=self._cwd, env=self._env)
        popen.wait()

        if popen.returncode != 0:
            perror('Command exited with status {}'.format(popen.returncode))

    def sudo_run(self, cmd):
        self.run('sudo {}'.format(cmd))

    def cd(self, cwd):
        msg = 'cd {}'.format(shlex.quote(cwd))
        print(colored(msg, 'cyan', attrs=['bold']))
        self._cwd = cwd

    def set_env(self, env):
        self._env = _get_full_env(env, self._paths)

        for key, val in self._env.items():
            _psetenv(key, val)

    def wget(self, url, output_path):
        cmd = 'wget {} -O {}'.format(shlex.quote(url), shlex.quote(output_path))
        self.run(cmd)

    def git_clone(self, clone_url, path):
        cmd = 'git clone {} {}'.format(shlex.quote(clone_url), shlex.quote(path))
        self.run(cmd)

    def git_checkout(self, treeish):
        cmd = 'git checkout {}'.format(shlex.quote(treeish))
        self.run(cmd)

    def mkdir_p(self, path):
        cmd = 'mkdir --verbose -p {}'.format(shlex.quote(path))
        self.run(cmd)

    def tar_x(self, path):
        cmd = 'tar -xvf {}'.format(shlex.quote(path))
        self.run(cmd)

    def bootstrap(self):
        self.run('./bootstrap')

    def configure(self, args):
        cmd = './configure --prefix={} {}'.format(shlex.quote(self._paths.usr),
                                                  args)
        self.run(cmd)

    def make(self, target=None, sudo=False):
        cmd = 'make -j{} V=1'.format(self._jobs)

        if target is not None:
            cmd += ' ' + shlex.quote(target)

        if sudo:
            fn = self.sudo_run
        else:
            fn = self.run

        fn(cmd)


class _Paths:
    def __init__(self, venv):
        self._venv = venv

    @property
    def venv(self):
        return self._venv

    @property
    def home(self):
        return os.path.join(self._venv, 'home')

    @property
    def usr(self):
        return os.path.join(self._venv, 'usr')

    @property
    def src(self):
        return os.path.join(self._venv, 'src')

    def project_src(self, name):
        return os.path.join(self.src, name)


def _name_from_archive_name(archive_name):
    return re.sub('\.(?:tar|zip|tgz).*', '', archive_name)


class VEnvCreator:
    def __init__(self, path, profile, verbose, jobs):
        self._paths = _Paths(os.path.abspath(path))
        self._runner = _Runner(verbose, jobs, self._paths)
        self._profile = profile
        self._verbose = verbose
        self._src_paths = {}
        self._create()

    def _create(self):
        _pinfo('Create LTTng virtual environment')

        # create virtual environment directory
        if os.path.exists(self._paths.venv):
            perror('Virtual environment path "{}" exists'.format(self._paths.venv))

        self._runner.mkdir_p(self._paths.venv)
        self._runner.mkdir_p(self._paths.home)

        # fetch sources and extract/checkout
        _pinfo('Fetch sources')
        self._fetch_sources()

        # build URCU first
        self._build_project('urcu', self._configure_make_install)

        # build LTTng-UST
        self._build_project('lttng-ust', self._configure_make_install)

        # build LTTng-tools
        self._build_lttng_tools()

        # build LTTng-modules
        self._build_lttng_modules()

        # build Babeltrace
        self._build_project('babeltrace', self._configure_make_install)

        # create activate script
        self._create_activate()

    def _create_activate(self):
        from vlttng.activate_template import activate_template

        env_items = []
        env = copy.deepcopy(self._profile.virt_env)
        _patch_env(env, self._paths)
        rm_keys = (
            'VLTTNG',
            'PATH',
            'LD_LIBRARY_PATH',
            'MANPATH',
            'PYTHONPATH',
            'LTTNG_HOME',
            'PS1',
        )

        for key in rm_keys:
            if key in env:
                del env[key]

        for key, val in env.items():
            setenv = 'export {}={}'.format(key.strip(), shlex.quote(str(val)))
            env_items.append(setenv)

        env_lines = '\n'.join(env_items)
        lttng_modules_src_path = self._src_paths.get('lttng-modules', '')
        activate = activate_template.format(venv_path=shlex.quote(self._paths.venv),
                                            lttng_modules_src_path=shlex.quote(lttng_modules_src_path),
                                            env=env_lines)
        activate_path = os.path.join(self._paths.venv, 'activate')
        _pinfo('Create activation script "{}"'.format(activate_path))

        with open(activate_path, 'w') as f:
            f.write(activate)

    def _fetch_sources(self):
        self._runner.mkdir_p(self._paths.src)
        self._runner.cd(self._paths.src)

        for project in self._profile.projects.values():
            source = project.source
            src_path = None

            if type(source) is vlttng.profile.HttpFtpSource:
                # download
                posix_path = PurePosixPath(source.url)
                filename = posix_path.name
                src_path = _name_from_archive_name(filename)
                self._runner.wget(source.url, filename)

                # extract
                self._runner.tar_x(filename)
            elif type(source) is vlttng.profile.GitSource:
                src_path = project.name

                # clone
                self._runner.git_clone(source.clone_url, project.name)

                # checkout
                self._runner.cd(self._paths.project_src(project.name))
                self._runner.git_checkout(source.checkout)
                self._runner.cd(self._paths.src)

            # keep where the source of this project is
            if src_path is not None:
                src_path = self._paths.project_src(src_path)
                self._src_paths[project.name] = src_path

    def _configure_make_install(self, project, add_args=None):
        # bootstrap?
        bootstrap = os.path.join(self._paths.project_src(project.name),
                                 'bootstrap')

        if os.path.isfile(bootstrap):
            self._runner.bootstrap()

        # configure
        args = project.configure

        if '--prefix' in project.configure:
            fmt = 'Project "{}": I would not pass the --prefix configure option if I were you: it is handled by vlttng'
            _pwarn(fmt.format(project.name))

        if add_args is not None:
            args += ' ' + add_args

        self._runner.configure(args)

        # make
        self._runner.make()

        # make install
        self._runner.make('install')

    def _build_project(self, name, build_fn, configure_add_args=None):
        project = self._profile.projects.get(name)

        if project is None:
            return

        _pinfo('Build and install {}'.format(name))
        self._runner.cd(self._src_paths[project.name])
        self._runner.set_env(project.build_env)
        build_fn(project)

    def _build_lttng_tools(self):
        project = self._profile.projects.get('lttng-tools')

        if project is None:
            return

        if '--with-lttng-ust-prefix' in project.configure or '--without-lttng-ust' in project.configure:
            msg = 'I would not pass the --with-lttng-ust-prefix/--without-lttng-ust configure option if I were you: they are handled by vlttng'
            _pwarn(msg)

        if 'lttng-ust' in self._profile.projects:
            add_args = '--with-lttng-ust-prefix={}'.format(shlex.quote(self._paths.usr))
        else:
            add_args = '--without-lttng-ust'

        build_fn = functools.partial(self._configure_make_install,
                                     add_args=add_args)
        self._build_project('lttng-tools', build_fn)

    def _build_lttng_modules(self):
        def build(project):
            self._runner.make()

        self._build_project('lttng-modules', build)

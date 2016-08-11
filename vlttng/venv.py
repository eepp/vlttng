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
    # PATH
    path = env.get('PATH', '')
    path = '{}:{}'.format(paths.bin, path)
    env['PATH'] = path

    # CPPFLAGS
    cppflags = env.get('CPPFLAGS', '')
    include_dir = os.path.join(paths.usr, 'include')
    cppflags += ' -I{}'.format(shlex.quote(include_dir))
    env['CPPFLAGS'] = cppflags

    # LDFLAGS
    ldflags = env.get('LDFLAGS', '')
    ldflags += ' -L{}'.format(shlex.quote(paths.lib))
    env['LDFLAGS'] = ldflags

    # LD_LIBRARY_PATH
    ld_library_path = env.get('LD_LIBRARY_PATH', '')
    ld_library_path = '{}:{}'.format(paths.lib, ld_library_path)
    env['LD_LIBRARY_PATH'] = ld_library_path

    # PKG_CONFIG_PATH
    pkg_config_path = env.get('PKG_CONFIG_PATH', '')
    pkg_config_path = '{}:{}'.format(paths.pkgconfig, pkg_config_path)
    env['PKG_CONFIG_PATH'] = pkg_config_path

    # PYTHONPATH
    if os.path.isdir(paths.lib):
        python_roots = []

        for filename in os.listdir(paths.lib):
            if filename.startswith('python'):
                python_root = os.path.join(paths.lib, filename)

                if os.path.isdir(python_root):
                    python_roots.append(python_root)

        site_packages = []

        for python_root in python_roots:
            for filename in os.listdir(python_root):
                if filename.endswith('-packages'):
                    site_package = os.path.join(python_root, filename)

                    if os.path.isdir(site_package):
                        site_packages.append(site_package)

        new_pythonpath = ':'.join(site_packages)
        pythonpath = env.get('PYTHONPATH', '')
        pythonpath = '{}:{}'.format(new_pythonpath, pythonpath)
        env['PYTHONPATH'] = pythonpath


def _get_full_env(env, paths):
    new_env = copy.deepcopy(os.environ)

    try:
        new_env.update(env)
    except:
        perror('Invalid environment in profile')

    _patch_env(new_env, paths)

    return new_env


class _Runner:
    def __init__(self, verbose, hide_export, jobs, paths):
        self._verbose = verbose
        self._hide_export = hide_export
        self._cwd = None
        self._env = None
        self._jobs = jobs
        self._paths = paths

    @property
    def cwd(self):
        return self._cwd

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

        if not self._hide_export:
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

    def cp_rv(self, src, dst):
        cmd = 'cp -rv {} {}'.format(shlex.quote(src), shlex.quote(dst))
        self.run(cmd)

    def ln_s(self, target, link):
        cmd = 'ln -s {} {}'.format(shlex.quote(target), shlex.quote(link))
        self.run(cmd)

    def tar_x(self, path, output_name):
        cmd = 'tar -xvf {} -C {} --strip-components=1'.format(shlex.quote(path),
                                                              shlex.quote(output_name))
        self.run(cmd)

    def rm_rf(self, path):
        # some basic protection
        no_rm_dirs = (
            os.path.expanduser('~'),
            '/',
            '/bin',
            '/boot',
            '/dev',
            '/etc',
            '/home',
            '/lib',
            '/lib64',
            '/opt',
            '/root',
            '/run',
            '/sbin',
            '/usr',
            '/var'
        )
        no_rm_dirs = [os.path.normpath(d) for d in no_rm_dirs]
        norm_path = os.path.normpath(path)

        if norm_path in no_rm_dirs:
            perror('Not removing protected directory "{}"'.format(norm_path))

        cmd = 'rm -rf {}'.format(shlex.quote(path))
        self.run(cmd)

    def configure(self, args):
        cmd = './configure --prefix={} {}'.format(shlex.quote(self._paths.usr),
                                                  args)
        self.run(cmd)

    def make(self, target=None, args=None, sudo=False):
        cmd = 'make -j{} V=1'.format(self._jobs)

        if target is not None:
            cmd += ' ' + shlex.quote(target)

        if args is not None:
            cmd += ' ' + args

        if sudo:
            fn = self.sudo_run
        else:
            fn = self.run

        fn(cmd)

    def setuppy_install(self):
        cmd = './setup.py install --prefix={}'.format(shlex.quote(self._paths.usr))
        self.run(cmd)

    def maven(self, args):
        cmd = 'mvn {}'.format(args)
        self.run(cmd)


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
    def bin(self):
        return os.path.join(self.usr, 'bin')

    @property
    def lib(self):
        return os.path.join(self.usr, 'lib')

    @property
    def pkgconfig(self):
        return os.path.join(self.lib, 'pkgconfig')

    @property
    def include(self):
        return os.path.join(self.usr, 'include')

    @property
    def opt(self):
        return os.path.join(self.usr, 'opt')

    @property
    def src(self):
        return os.path.join(self._venv, 'src')

    @property
    def share(self):
        return os.path.join(self.usr, 'share')

    @property
    def share_java(self):
        return os.path.join(self.share, 'java')

    def project_src(self, name):
        return os.path.join(self.src, name)


class VEnvCreator:
    def __init__(self, path, profile, force, verbose, jobs, hide_export):
        self._paths = _Paths(os.path.abspath(path))
        self._runner = _Runner(verbose, hide_export, jobs, self._paths)
        self._profile = profile
        self._force = force
        self._verbose = verbose
        self._src_paths = {}
        self._create()

    def _validate_profile(self):
        projects = self._profile.projects

        if 'lttng-tools' in projects or 'lttng-ust' in projects:
            if 'urcu' not in projects:
                _pwarn('The "lttng-tools"/"lttng-ust" project will use the system\'s Userspace RCU')

        if 'lttng-analyses' in projects:
            if 'babeltrace' not in projects:
                _pwarn('The "lttng-analyses" project will use the system\'s Babeltrace')
            elif '--enable-python-bindings' not in projects['babeltrace'].configure:
                _pwarn('Configuring "babeltrace" project with "--enable-python-bindings" (caused by "lttng-analyses")')
                configure = projects['babeltrace'].configure
                configure = configure.replace('--disable-python-bindings', '')
                configure = configure.replace('--enable-python-bindings=no', '')
                configure += ' --enable-python-bindings'
                projects['babeltrace'].configure = configure

        if 'babeltrace' in projects:
            project = projects['babeltrace']

            if 'glib' not in projects:
                _pwarn('The "babeltrace" project will use the system\'s GLib')

            if '--enable-debug-info' in project.configure or '--disable-debug-info' not in project.configure:
                if 'elfutils' not in projects:
                    _pwarn('The "babeltrace" project will use the system\'s elfutils')

        if 'lttng-tools' in projects:
            if 'libxml2' not in projects:
                _pwarn('The "lttng-tools" project will use the system\'s libxml2')

    def _create(self):
        self._validate_profile()

        _pinfo('Create LTTng virtual environment')

        # create virtual environment directory
        if os.path.exists(self._paths.venv):
            if self._force:
                _pwarn('Virtual environment path "{}" exists: removing directory'.format(self._paths.venv))
                self._runner.rm_rf(self._paths.venv)
            else:
                perror('Virtual environment path "{}" exists'.format(self._paths.venv))

        self._runner.mkdir_p(self._paths.venv)
        self._runner.mkdir_p(self._paths.home)
        self._runner.mkdir_p(self._paths.bin)
        self._runner.mkdir_p(self._paths.lib)
        self._runner.mkdir_p(self._paths.include)
        self._runner.mkdir_p(self._paths.opt)
        self._runner.mkdir_p(self._paths.share_java)

        # fetch sources and extract/checkout
        _pinfo('Fetch sources')
        self._fetch_sources()

        # build URCU first
        self._build_project('urcu', self._configure_make_install)

        # build LTTng-UST
        self._build_lttng_ust()

        # build libxml2
        self._build_project('libxml2', self._configure_make_install)

        # build LTTng-tools
        self._build_lttng_tools()

        # build LTTng-modules
        self._build_lttng_modules()

        # build GLib
        self._build_project('glib', self._configure_make_install)

        # build elfutils
        self._build_project('elfutils', self._configure_make_install)

        # build Babeltrace
        self._build_project('babeltrace', self._configure_make_install)

        # build LTTng-analyses
        self._build_lttng_analyses()

        # build Trace Compass
        self._build_tracecompass()

        # create activate script
        self._create_activate()

    def _create_activate(self):
        from vlttng.activate_template import activate_template

        env_items = []
        unenv_items = []
        env = copy.deepcopy(self._profile.virt_env)
        _patch_env(env, self._paths)

        # the activation template explicitly defines those environment
        # variables, so they must not be overridden by the user or by us.
        rm_keys = (
            'VLTTNG',
            'PATH',
            'CPPFLAGS',
            'LDFLAGS',
            'LD_LIBRARY_PATH',
            'MANPATH',
            'PKG_CONFIG_PATH',
            'PYTHONPATH',
            'LTTNG_HOME',
            'PS1',
            'MODPROBE_OPTIONS',
        )

        for key in rm_keys:
            if key in env:
                del env[key]

        for key, val in env.items():
            key = key.strip()
            env_items.append('_VLTTNG_OLD_{e}="${e}"'.format(e=key))
            setenv = 'export {}={}'.format(key, shlex.quote(str(val)))
            env_items.append(setenv)
            unenv_items.append('    {e}="$_VLTTNG_OLD_{e}"'.format(e=key))
            unenv_items.append('    unset _VLTTNG_OLD_{}'.format(key))

        env_lines = '\n'.join(env_items)
        unenv_lines = '\n'.join(unenv_items)
        lttng_modules_src_path = self._src_paths.get('lttng-modules', '')
        has_modules = '1' if 'lttng-modules' in self._profile.projects else '0'
        has_java = '0'

        if 'lttng-ust' in self._profile.projects:
            configure = self._profile.projects['lttng-ust'].configure

            if '--enable-java-agent' in configure:
                has_java = '1'

        activate = activate_template.format(venv_path=shlex.quote(self._paths.venv),
                                            has_modules=has_modules,
                                            has_java=has_java,
                                            env=env_lines,
                                            unenv=unenv_lines)
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
                src_path = project.name

                # download
                posix_path = PurePosixPath(source.url)
                filename = posix_path.name
                self._runner.wget(source.url, filename)

                # extract
                self._runner.mkdir_p(self._paths.project_src(project.name))
                self._runner.tar_x(filename, project.name)
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
        for f in ('bootstrap', 'bootstrap.sh', 'autogen', 'autogen.sh',):
            bootstrap = os.path.join(self._paths.project_src(project.name), f)

            if os.path.isfile(bootstrap):
                self._runner.run('./{}'.format(f))
                break

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

    def _build_lttng_ust(self):
        def build(project):
            if '--enable-java-agent-all' in project.configure or '--enable-java-agent-log4j' in project.configure:
                cwd = self._runner.cwd

                # get Apache log4j 1.2
                log4j_name = 'log4j-1.2.17'
                log4j_tarball = '{}.tar.gz'.format(log4j_name)
                log4j_jar = '{}.jar'.format(log4j_name)
                log4j_installed_jar = os.path.join(self._paths.share_java, 'log4j.jar')
                self._runner.cd(self._paths.src)
                self._runner.wget('http://apache.mirror.gtcomm.net/logging/log4j/1.2.17/{}'.format(log4j_tarball),
                                  log4j_tarball)

                # extract
                self._runner.mkdir_p(log4j_name)
                self._runner.tar_x(log4j_tarball, log4j_name)

                # install
                self._runner.cp_rv(os.path.join(log4j_name, log4j_jar),
                                   log4j_installed_jar)

                # update $CLASSPATH
                classpath = os.environ.get('CLASSPATH', '')
                classpath = '{}:{}'.format(log4j_installed_jar, classpath)
                self._runner.set_env({
                    'CLASSPATH': classpath
                })

                self._runner.cd(cwd)

            # build and install LTTng-UST
            self._configure_make_install(project)

        project = self._profile.projects.get('lttng-ust')

        if project is None:
            return

        self._build_project('lttng-ust', build)

    def _build_lttng_modules(self):
        def build(project):
            self._runner.make()
            install_path = shlex.quote(self._paths.usr)
            self._runner.make('modules_install', 'INSTALL_MOD_PATH={}'.format(install_path))
            self._runner.run('depmod --all --basedir {}'.format(shlex.quote(self._paths.usr)))

        self._build_project('lttng-modules', build)

    def _build_lttng_analyses(self):
        def build(project):
            self._runner.setuppy_install()

        self._build_project('lttng-analyses', build)

    def _build_tracecompass(self):
        def finalize(src):
            dst = os.path.join(self._paths.opt, 'tracecompass')
            self._runner.cp_rv(src, dst)
            link = os.path.join(self._paths.bin, 'tracecompass')
            self._runner.ln_s(os.path.join(dst, 'tracecompass'), link)

        def build_from_tarball(project):
            finalize(self._paths.project_src('tracecompass'))

        def build_from_git(project):
            self._runner.maven('clean install -Dmaven.test.skip=true')
            src = os.path.join('rcp',
                               'org.eclipse.tracecompass.rcp.product',
                               'target',
                               'products',
                               'org.eclipse.tracecompass.rcp',
                               'linux',
                               'gtk',
                               'x86_64',
                               'trace-compass')
            finalize(src)

        project = self._profile.projects.get('tracecompass')

        if project is None:
            return

        if type(project.source) is vlttng.profile.HttpFtpSource:
            build_fn = build_from_tarball
        else:
            build_fn = build_from_git

        self._build_project('tracecompass', build_fn)

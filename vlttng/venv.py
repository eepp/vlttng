# The MIT License (MIT)
#
# Copyright (c) 2016-2017 Philippe Proulx <eepp.ca>
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
import stat
import copy
import shlex
import os.path
import functools
import subprocess
import vlttng.profile
from termcolor import colored
from vlttng.utils import perror
from pathlib import PurePosixPath


def _sq(t):
    return shlex.quote(t)


def _pcmd(cmd):
    print(colored(cmd, attrs=['bold']))


def _psetenv(key, val):
    setenv = 'export {}={}'.format(key.strip(), _sq(str(val)))
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
    cppflags += ' -I{}'.format(_sq(include_dir))
    env['CPPFLAGS'] = cppflags

    # LDFLAGS
    ldflags = env.get('LDFLAGS', '')
    ldflags += ' -L{}'.format(_sq(paths.lib))
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
    def __init__(self, verbose, hide_export, paths):
        self._verbose = verbose
        self._hide_export = hide_export
        self._cwd = None
        self._env = None
        self._paths = paths

    @property
    def cwd(self):
        return self._cwd

    def _run_line(self, cmd):
        _pcmd(cmd)
        stdio = None if self._verbose else subprocess.DEVNULL
        popen = subprocess.Popen(cmd, stdin=None, stdout=stdio, stderr=stdio,
                                 shell=True, cwd=self._cwd, env=self._env)
        popen.wait()

        if popen.returncode != 0:
            perror('Command exited with status {}'.format(popen.returncode))

    def run(self, cmd):
        if type(cmd) is str:
            self._run_line(cmd)
        elif type(cmd) is list:
            for line in cmd:
                self._run_line(line)

    def cd(self, cwd):
        msg = 'cd {}'.format(_sq(cwd))
        print(colored(msg, 'cyan', attrs=['bold']))
        self._cwd = cwd

    def set_env(self, env):
        self._env = _get_full_env(env, self._paths)

        if not self._hide_export:
            for key in sorted(self._env):
                _psetenv(key, self._env[key])

    def wget(self, url, output_path):
        cmd = 'wget {} -O {}'.format(_sq(url), _sq(output_path))
        self.run(cmd)

    def git_clone(self, clone_url, path):
        cmd = 'git clone {} {}'.format(_sq(clone_url), _sq(path))
        self.run(cmd)

    def git_checkout(self, treeish):
        cmd = 'git checkout {}'.format(_sq(treeish))
        self.run(cmd)

    def mkdir_p(self, path):
        cmd = 'mkdir -v -p {}'.format(_sq(path))
        self.run(cmd)

    def cp_rv(self, src, dst):
        cmd = 'cp -rv {} {}'.format(_sq(src), _sq(dst))
        self.run(cmd)

    def ln_s(self, target, link):
        cmd = 'ln -s {} {}'.format(_sq(target), _sq(link))
        self.run(cmd)

    def tar_x(self, path, output_name):
        cmd = 'tar -xvf {} -C {} --strip-components=1'.format(_sq(path),
                                                              _sq(output_name))
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

        cmd = 'rm -rf {}'.format(_sq(path))
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

    @property
    def log4j_jar(self):
        return os.path.join(self.share_java, 'log4j.jar')

    def project_src(self, name):
        return os.path.join(self.src, name)


class _ProjectInstructions:
    def __init__(self, project, add_env=None, conf_lines=None,
                 build_lines=None, install_lines=None, uninstall_lines=None):
        self._project = project
        self.add_env = add_env
        self.conf_lines = conf_lines
        self.build_lines = build_lines
        self.install_lines = install_lines
        self.uninstall_lines = uninstall_lines

    @property
    def project(self):
        return self._project


class VEnvCreator:
    _LOG4J_NAME = 'log4j-1.2.17'

    def __init__(self, path, profile, force, verbose, jobs, hide_export):
        self._paths = _Paths(os.path.abspath(path))
        self._runner = _Runner(verbose, hide_export, self._paths)
        self._jobs = jobs
        self._profile = profile
        self._force = force
        self._verbose = verbose
        self._src_paths = {}
        self._project_instructions = {}
        self._create_project_instructions_cbs = {
            'babeltrace': self._create_project_instructions_generic_autotools,
            'elfutils': self._create_project_instructions_generic_autotools,
            'glib': self._create_project_instructions_generic_autotools,
            'libxml2': self._create_project_instructions_generic_autotools,
            'lttng-analyses': self._create_project_instructions_lttng_analyses,
            'lttng-modules': self._create_project_instructions_lttng_modules,
            'lttng-tools': self._create_project_instructions_lttng_tools,
            'lttng-ust': self._create_project_instructions_lttng_ust,
            'popt': self._create_project_instructions_generic_autotools,
            'tracecompass': self._create_project_instructions_tracecompass,
            'lttng-scope': self._create_project_instructions_lttng_scope,
            'urcu': self._create_project_instructions_generic_autotools,
        }
        self._create()

    def _get_make(self):
        return 'make -j{} V=1'.format(self._jobs if self._jobs is not None else '')

    def _check_man_pages(self, name, project):
        if type(project.source) is not vlttng.profile.GitSource:
            return

        disable_man_pages = False

        if '--enable-man-pages=no' not in project.configure and '--disable-man-pages' not in project.configure:
            try:
                subprocess.check_call('asciidoc --version', shell=True,
                                      stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL,
                                      timeout=1)

                try:
                    subprocess.check_call('xmlto --version', shell=True,
                                          stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL,
                                          timeout=1)
                except:
                    _pwarn('{} man pages will not be built because vlttng cannot find and execute `xmlto`'.format(name))
                    disable_man_pages = True
            except:
                _pwarn('{} man pages will not be built because vlttng cannot find and execute `asciidoc`'.format(name))
                disable_man_pages = True

        if disable_man_pages:
            project.configure += ' --disable-man-pages'

    def _validate_profile(self):
        def check_dep(project_name, dep_name):
            if project_name in projects and dep_name not in projects:
                _pwarn('The "{}" project will use an external "{}"'.format(project_name, dep_name))

        projects = self._profile.projects
        check_dep('lttng-tools', 'urcu')
        check_dep('lttng-ust', 'urcu')
        check_dep('lttng-analyses', 'babeltrace')
        check_dep('babeltrace', 'glib')
        check_dep('lttng-tools', 'libxml2')
        check_dep('lttng-tools', 'popt')
        check_dep('babeltrace', 'popt')

        if 'lttng-analyses' in projects:
            if 'babeltrace' in projects and '--enable-python-bindings' not in projects['babeltrace'].configure:
                _pwarn('Configuring "babeltrace" project with "--enable-python-bindings" (caused by "lttng-analyses")')
                configure = projects['babeltrace'].configure
                configure = configure.replace('--disable-python-bindings', '')
                configure = configure.replace('--enable-python-bindings=no', '')
                configure += ' --enable-python-bindings'
                projects['babeltrace'].configure = configure

        if 'babeltrace' in projects:
            project = projects['babeltrace']

            if '--enable-debug-info' in project.configure or '--disable-debug-info' not in project.configure:
                check_dep('babeltrace', 'elfutils')

        if 'lttng-tools' in projects:
            self._check_man_pages('LTTng-tools', projects['lttng-tools'])

        if 'lttng-ust' in projects:
            self._check_man_pages('LTTng-UST', projects['lttng-ust'])

    def _create_project_instructions_lttng_tools(self, project):
        lttng_ust_opts = (
            '--with-lttng-ust-prefix',
            '--without-lttng-ust',
            '--disable-lttng-ust',
            '--enable-lttng-ust',
        )

        for ust_opt in lttng_ust_opts:
            if ust_opt in project.configure:
                fmt = 'I would not pass the {} configure option if I were you: they are handled by vlttng'
                msg = fmt.format(ust_opt)
                _pwarn(msg)

        add_args = ''

        if 'lttng-ust' not in self._profile.projects:
            # LTTng-tools prior to v2.8 uses a different flag to turn
            # off LTTng-UST support. We add both to the configure script
            # arguments: the unsupported one will be ignored.
            add_args = '--without-lttng-ust --disable-lttng-ust'

        add_args += ' --disable-kmod --without-kmod'

        return self._create_project_instructions_generic_autotools(project, add_args)

    def _create_project_instructions_lttng_ust(self, project):
        instructions = self._create_project_instructions_generic_autotools(project)
        instructions.add_env = {
            'CLASSPATH': self._paths.log4j_jar,
        }

        return instructions

    def _create_project_instructions_lttng_modules(self, project):
        build_lines = [
            self._get_make(),
        ]
        sq_install_path = _sq(self._paths.usr)
        install_lines = [
            'make modules_install INSTALL_MOD_PATH={}'.format(sq_install_path),
            'depmod --all --basedir={}'.format(sq_install_path),
        ]

        return _ProjectInstructions(project, build_lines=build_lines,
                                    install_lines=install_lines)

    def _create_project_instructions_lttng_analyses(self, project):
        build_lines = [
            './setup.py build',
        ]
        install_lines = [
            './setup.py install --prefix={}'.format(_sq(self._paths.usr))
        ]

        return _ProjectInstructions(project, build_lines=build_lines,
                                    install_lines=install_lines)

    def _create_project_instructions_tracecompass(self, project):
        dst = os.path.join(self._paths.opt, 'tracecompass')
        install_lines = []

        if type(project.source) is vlttng.profile.HttpFtpSource:
            src = self._paths.project_src('tracecompass')
        else:
            install_lines = [
                'mvn clean install -Dmaven.test.skip=true',
            ]
            src = os.path.join('rcp',
                               'org.eclipse.tracecompass.rcp.product',
                               'target',
                               'products',
                               'org.eclipse.tracecompass.rcp',
                               'linux',
                               'gtk',
                               'x86_64',
                               'trace-compass')

        link = os.path.join(self._paths.bin, 'tracecompass')
        install_lines += [
            'cp -rv {} {}'.format(_sq(src), _sq(dst)),
            'ln -s {} {}'.format(_sq(os.path.join(dst, 'tracecompass')),
                                 _sq(link)),
        ]

        return _ProjectInstructions(project, install_lines=install_lines)

    def _create_project_instructions_lttng_scope(self, project):
        jar_dst = os.path.join(self._paths.opt, 'lttng-scope.jar')

        if type(project.source) is vlttng.profile.HttpFtpSource:
            jar_src = os.path.join(self._paths.src, 'lttng-scope.jar')
            install_lines = [
                'cp -v {} {}'.format(_sq(jar_src), _sq(jar_dst)),
            ]
        else:
            jar_dir = os.path.join('lttng-scope', 'target')
            install_lines = [
                'mvn clean install -Dmaven.test.skip=true -DskipTests',
                'cp -v {}/*with-dependencies.jar {}'.format(_sq(jar_dir),
                                                             _sq(jar_dst)),
            ]

        return _ProjectInstructions(project, install_lines=install_lines)

    def _create_project_instructions_generic_autotools(self, project, add_conf_args=None):
        conf_lines = []
        build_lines = [self._get_make()]
        install_lines = ['make install']
        uninstall_lines = ['make uninstall']

        # bootstrap?
        project_src = self._paths.project_src(project.name)

        if not os.path.isfile(os.path.join(project_src, 'configure')):
            for f in ('bootstrap', 'bootstrap.sh', 'autogen', 'autogen.sh',):
                bootstrap = os.path.join(project_src, f)

                if os.path.isfile(bootstrap):
                    conf_lines.append('./{}'.format(f))
                    break

        # configure
        conf_args = project.configure

        if '--prefix' in project.configure:
            fmt = 'Project "{}": I would not pass the --prefix configure option if I were you: it is handled by vlttng'
            _pwarn(fmt.format(project.name))

        if add_conf_args is not None:
            conf_args += ' ' + add_conf_args

        conf_line = './configure --prefix={} {}'.format(_sq(self._paths.usr),
                                                        conf_args)
        conf_lines.append(conf_line)

        return _ProjectInstructions(project, conf_lines=conf_lines,
                                    build_lines=build_lines,
                                    install_lines=install_lines,
                                    uninstall_lines=uninstall_lines)

    def _create_project_instructions(self):
        for name, project in self._profile.projects.items():
            self._project_instructions[name] = self._create_project_instructions_cbs[name](project)

    def _create(self):
        self._validate_profile()

        _pinfo('Create LTTng virtual environment')

        # create virtual environment directory
        if os.path.exists(self._paths.venv):
            if self._force:
                _pwarn('Virtual environment path "{}" exists: removing directory'.format(self._paths.venv))
                self._runner.rm_rf(self._paths.venv)
            else:
                perror('Virtual environment path "{}" exists (use --force to overwrite)'.format(self._paths.venv))

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

        # create build instructions for projects to build
        self._create_project_instructions()

        # build projects in this order
        self._build_project('urcu')
        self._build_project('popt')
        self._build_lttng_ust()
        self._build_project('libxml2')
        self._build_project('lttng-tools')
        self._build_project('lttng-modules')
        self._build_project('glib')
        self._build_project('elfutils')
        self._build_project('babeltrace')
        self._build_project('lttng-analyses')
        self._build_project('tracecompass')
        self._build_project('lttng-scope')

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
            env_items.append('vlttng-save-env {}'.format(key))
            setenv = 'export {}={}'.format(key, _sq(str(val)))
            env_items.append(setenv)
            unenv_items.append('    vlttng-restore-env {}'.format(key))

        env_lines = '\n'.join(env_items)
        unenv_lines = '\n'.join(unenv_items)
        lttng_modules_src_path = self._src_paths.get('lttng-modules', '')
        has_modules = '1' if 'lttng-modules' in self._profile.projects else '0'
        has_lttng_scope = '1' if 'lttng-scope' in self._profile.projects else '0'
        has_java = '0'

        if 'lttng-ust' in self._profile.projects:
            configure = self._profile.projects['lttng-ust'].configure

            if '--enable-java-agent' in configure:
                has_java = '1'

        activate = activate_template.format(venv_path=_sq(self._paths.venv),
                                            has_modules=has_modules,
                                            has_java=has_java,
                                            has_lttng_scope=has_lttng_scope,
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
                # download
                posix_path = PurePosixPath(source.url)

                if project.name == 'lttng-scope':
                    src_path = self._paths.src
                    filename = 'lttng-scope.jar'
                else:
                    src_path = project.name
                    filename = posix_path.name

                self._runner.wget(source.url, filename)

                # extract
                if not filename.endswith('.jar'):
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

    def _build_lttng_ust(self):
        project = self._profile.projects.get('lttng-ust')

        if project is None:
            return

        if '--enable-java-agent-all' in project.configure or '--enable-java-agent-log4j' in project.configure:
            # get Apache log4j 1.2
            log4j_name = 'log4j-1.2.17'
            log4j_tarball = '{}.tar.gz'.format(log4j_name)
            log4j_jar = '{}.jar'.format(log4j_name)
            _pinfo('Download Apache log4j')
            self._runner.cd(self._paths.src)
            self._runner.wget('http://apache.mirror.gtcomm.net/logging/log4j/1.2.17/{}'.format(log4j_tarball),
                              log4j_tarball)

            # extract
            self._runner.mkdir_p(log4j_name)
            self._runner.tar_x(log4j_tarball, log4j_name)

            # install
            self._runner.cp_rv(os.path.join(log4j_name, log4j_jar),
                               self._paths.log4j_jar)

        self._build_project('lttng-ust')

    def _get_build_env_from_instructions(self, instructions):
        build_env = copy.deepcopy(self._profile.build_env)
        build_env.update(instructions.project.build_env)

        if instructions.add_env is not None:
            build_env.update(instructions.add_env)

        return build_env

    def _build_project(self, name):
        instructions = self._project_instructions.get(name)

        if instructions is None:
            return

        build_env = self._get_build_env_from_instructions(instructions)
        self._runner.set_env(build_env)
        self._runner.cd(self._src_paths[instructions.project.name])

        if instructions.conf_lines is not None:
            _pinfo('Configure {}'.format(name))
            self._runner.run(instructions.conf_lines)

        if instructions.build_lines is not None:
            _pinfo('Build {}'.format(name))
            self._runner.run(instructions.build_lines)

        if instructions.install_lines is not None:
            _pinfo('Install {}'.format(name))
            self._runner.run(instructions.install_lines)

        self._create_scripts(instructions)

    def _create_executable_script(self, script_name, content):
        script_path = os.path.join(self._paths.venv,
                                   '{}.bash'.format(script_name))

        with open(script_path, 'w') as f:
            f.write(content)

        st = os.stat(script_path)
        os.chmod(script_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _create_conf_script(self, instructions, name, exports, src_path):
        from vlttng.conf_template import conf_template as tmpl

        conf_lines = ''

        if instructions.conf_lines is not None:
            conf_lines = '\n'.join(instructions.conf_lines)

        conf = tmpl.format(name=name, src_path=_sq(src_path),
                           conf_lines=conf_lines, exports=exports)
        self._create_executable_script('conf-{}'.format(name), conf)

    def _create_build_script(self, instructions, name, exports, src_path):
        from vlttng.build_template import build_template as tmpl

        build_lines = ''

        if instructions.build_lines is not None:
            build_lines = '\n'.join(instructions.build_lines)

        build = tmpl.format(name=name, src_path=_sq(src_path),
                            build_lines=build_lines, exports=exports)
        self._create_executable_script('build-{}'.format(name), build)

    def _create_install_script(self, instructions, name, exports, src_path):
        from vlttng.install_template import install_template as tmpl

        install_lines = ''

        if instructions.install_lines is not None:
            install_lines = '\n'.join(instructions.install_lines)

        install = tmpl.format(name=name, src_path=_sq(src_path),
                              install_lines=install_lines, exports=exports)
        self._create_executable_script('install-{}'.format(name), install)

    def _create_update_script(self, instructions, name, exports, src_path):
        from vlttng.update_template import update_template as tmpl

        gitref = instructions.project.source.checkout
        uninstall_lines = ''

        if instructions.uninstall_lines is not None:
            uninstall_lines = '\n'.join(instructions.uninstall_lines)

        update = tmpl.format(name=name, src_path=_sq(src_path),
                             uninstall_lines=uninstall_lines, gitref=gitref,
                             exports=exports)
        self._create_executable_script('update-{}'.format(name), update)

    def _create_scripts(self, instructions):
        name = instructions.project.name
        src_path = self._src_paths[name]
        build_env = self._get_build_env_from_instructions(instructions)
        build_env = _get_full_env(build_env, self._paths)
        export_lines = []

        for key in sorted(build_env):
            value = build_env[key]
            export_lines.append('export {}={}'.format(key, _sq(value)))

        exports = '\n'.join(export_lines)

        # always generate those
        self._create_conf_script(instructions, name, exports, src_path)
        self._create_build_script(instructions, name, exports, src_path)
        self._create_install_script(instructions, name, exports, src_path)

        if type(instructions.project.source) is vlttng.profile.GitSource:
            # only generate update script if it's a Git source
            self._create_update_script(instructions, name, exports, src_path)

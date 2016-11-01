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

import yaml
import copy


class UnknownSourceFormat(Exception):
    def __init__(self, source):
        self._source = source

    @property
    def source(self):
        return self._source


class InvalidProfile(Exception):
    pass


class ParseError(Exception):
    pass


class InvalidOverride(Exception):
    pass


class GitSource:
    def __init__(self, clone_url, checkout):
        self._clone_url = clone_url
        self._checkout = checkout

    @property
    def clone_url(self):
        return self._clone_url

    @property
    def checkout(self):
        return self._checkout


class HttpFtpSource:
    def __init__(self, url):
        self._url = url

    @property
    def url(self):
        return self._url


class Project:
    def __init__(self, name, source, configure, build_env):
        self._name = name
        self._source = source
        self._configure = configure
        self._build_env = build_env

    @property
    def name(self):
        return self._name

    @property
    def source(self):
        return self._source

    @property
    def configure(self):
        return self._configure

    @configure.setter
    def configure(self, value):
        self._configure = value

    @property
    def build_env(self):
        return self._build_env


class Profile:
    def __init__(self, virt_env, build_env, projects):
        self._virt_env = virt_env
        self._build_env = build_env
        self._projects = projects

    @property
    def virt_env(self):
        return self._virt_env

    @property
    def build_env(self):
        return self._build_env

    @property
    def projects(self):
        return self._projects


class Override:
    OP_REPLACE = 'replace'
    OP_APPEND = 'append'
    OP_REMOVE = 'remove'

    def __init__(self, path, op, rep):
        if len(path) is 0:
            raise InvalidOverride('Empty override path')

        self._path = path
        self._op = op
        self._rep = rep

    @property
    def path(self):
        return self._path

    @property
    def op(self):
        return self._op

    @property
    def rep(self):
        return self._rep

    def apply(self, node):
        # find the root node in which to override a property and the
        # remaining path from where the existing property is found
        common_node = node
        remaining_path = self._path

        for index, key in enumerate(self._path[:-1]):
            if key in common_node:
                common_node = common_node[key]

                if not isinstance(common_node, dict):
                    fmt = 'Cannot override a non-associative array property ("{}") with an associative array'
                    raise InvalidOverride(fmt.format(key))

                remaining_path = self._path[index + 1:]
                continue
            else:
                break

        # create new property from remaining path
        cur_node = common_node
        prop_key = remaining_path[-1]

        if self._op in (Override.OP_REPLACE, Override.OP_APPEND):
            if remaining_path:
                for key in remaining_path[:-1]:
                    cur_node[key] = {}
                    cur_node = cur_node[key]

                if prop_key not in cur_node:
                    cur_node[prop_key] = ''

        # apply
        if self._op == Override.OP_REPLACE:
            cur_node[prop_key] = self._rep
        elif self._op == Override.OP_APPEND:
            if prop_key == 'configure':
                cur_node[prop_key] += ' '

            cur_node[prop_key] += self._rep
        elif self._op == Override.OP_REMOVE:
            del cur_node[prop_key]


def _source_from_project_node(project_node):
    source = project_node['source']

    if source.startswith('git://') or source.endswith('.git') or 'checkout' in project_node:
        checkout = 'master'

        if 'checkout' in project_node:
            checkout_node = project_node['checkout']

            if checkout_node is not None:
                checkout = checkout_node

        return GitSource(source, checkout)

    if source.startswith('http://') or source.startswith('https://') or source.startswith('ftp://'):
        return HttpFtpSource(source)

    raise UnknownSourceFormat(source)


def _merge_envs(enva, envb):
    env = copy.deepcopy(enva)
    env.update(envb)

    return env


def _project_from_project_node(name, project_node, base_build_env):
    source = _source_from_project_node(project_node)
    configure = ''
    build_env = {}

    if 'configure' in project_node:
        configure_node = project_node['configure']

        if configure_node is not None:
            configure = str(configure_node)

    if 'build-env' in project_node:
        build_env_node = project_node['build-env']

        if build_env_node is not None:
            build_env = _merge_envs(base_build_env, build_env_node)
    else:
        build_env = copy.deepcopy(base_build_env)

    return Project(name, source, configure, build_env)


def _validate_projects(projects):
    valid_project_names = (
        'babeltrace',
        'elfutils',
        'glib',
        'libxml2',
        'lttng-analyses',
        'lttng-modules',
        'lttng-tools',
        'lttng-ust',
        'popt',
        'tracecompass',
        'urcu',
    )

    for name in projects:
        if name not in valid_project_names:
            raise InvalidProfile('Unknown project name: "{}"'.format(name))


def _merge_nodes(base, patch):
    if isinstance(base, dict) and isinstance(patch, dict):
        for k, v in patch.items():
            if isinstance(v, dict) and k in base:
                _merge_nodes(base[k], v)
            else:
                if k == 'configure' and type(v) is str:
                    if k not in base:
                        base[k] = ''

                    base[k] += ' {}'.format(v)
                else:
                    base[k] = v


def _from_yaml_files(paths, ignored_projects, overrides, verbose):
    root_node = {}

    for path in paths:
        with open(path) as f:
            patch_root_node = yaml.load(f)
            _merge_nodes(root_node, patch_root_node)

    for override in overrides:
        override.apply(root_node)

    if verbose:
        print('Effective profile:')
        print()
        print(yaml.dump(root_node, explicit_start=True, explicit_end=True,
                        indent=2, default_flow_style=False))

    build_env = root_node.get('build-env', {})
    virt_env = root_node.get('virt-env', {})
    projects = {}

    for name, project_node in root_node['projects'].items():
        if name in ignored_projects:
            continue

        if project_node is None:
            continue

        project = _project_from_project_node(name, project_node, build_env)
        projects[name] = project

    _validate_projects(projects)

    return Profile(virt_env, build_env, projects)


def from_yaml_files(paths, ignored_projects, overrides, verbose):
    try:
        return _from_yaml_files(paths, ignored_projects, overrides, verbose)
    except (UnknownSourceFormat, InvalidProfile):
        raise
    except Exception as e:
        raise ParseError() from e

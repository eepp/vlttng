import logging
import sys
import findtb
import semver
import yaml
import os.path


def _find_tarballs(logger):
    project_urls = {
        'babeltrace': 'https://www.efficios.com/files/babeltrace/',
        'babeltrace2': 'https://www.efficios.com/files/babeltrace/',
        'elfutils': 'https://sourceware.org/elfutils/ftp/',
        'glib': 'https://ftp.gnome.org/pub/gnome/sources/glib/',
        'libxml2': 'ftp://xmlsoft.org/libxml2/',
        'lttng-modules': 'https://lttng.org/files/lttng-modules/',
        'lttng-tools': 'https://lttng.org/files/lttng-tools/',
        'lttng-ust': 'https://lttng.org/files/lttng-ust/',
        'userspace-rcu': 'https://lttng.org/files/urcu/',
    }

    tbs = set()

    for project_name, url in project_urls.items():
        logger.info(f'Finding `{project_name}` tarballs.')
        project_tbs = findtb.find_tarballs(project_name, url, logger)
        logger.info(f'Found {len(project_tbs)} tarballs for `{project_name}`.')
        tbs |= project_tbs

    return tbs


def _create_basic_profile(tb, conf=None, project_name=None):
    if project_name is None:
        project_name = tb.project_name

    profile = {
        'projects': {
            project_name: {
                'source': tb.url,
            },
        },
    }

    if conf is not None:
        profile['projects'][project_name]['configure'] = conf

    return profile


def _create_babeltrace_profile(tb):
    if tb.version.major != 1:
        return

    return _create_basic_profile(tb)


def _create_elfutils_profile(tb):
    conf = '--with-zlib --without-bzlib --with-lzma'
    return _create_basic_profile(tb, conf)


def _create_glib_profile(tb):
    conf = '--with-pcre=internal --disable-xattr --disable-selinux ' + \
           '--disable-dtrace --disable-systemtap --disable-gtk-doc ' + \
           '--disable-man --disable-coverage'
    return _create_basic_profile(tb, conf)


def _create_libxml2_profile(tb):
    conf = '--without-coverage --with-threads --without-python'
    return _create_basic_profile(tb, conf)


def _create_urcu_profile(tb):
    return _create_basic_profile(tb, project_name='urcu')


_create_profile_funcs = {
    'babeltrace': _create_babeltrace_profile,
    'elfutils': _create_elfutils_profile,
    'glib': _create_glib_profile,
    'libxml2': _create_libxml2_profile,
    'userspace-rcu': _create_urcu_profile,
}


def _create_yaml_profile(tb, out_dir, logger):
    if type(tb.version) is not semver.VersionInfo:
        return

    if tb.version.build is not None:
        return

    func = _create_profile_funcs.get(tb.project_name, _create_basic_profile)
    profile = func(tb)

    if profile is None:
        return

    prefix = tb.project_name

    if prefix == 'userspace-rcu':
        prefix = 'urcu'

    path = os.path.join(out_dir, f'{prefix}-{tb.version}.yml')
    logger.info(f'Writing profile `{path}`.')

    with open(path, 'w') as f:
        yaml.dump(profile, f)


def _get_logger():
    logging.basicConfig(style='{',
                        format='::: {asctime} {name:8s} [{levelname:8s}] {message}')
    logger = logging.getLogger('main')
    logger.setLevel(logging.INFO)
    return logger


def _create_profiles(out_dir):
    logger = _get_logger()
    tbs = _find_tarballs(logger)

    for tb in tbs:
        _create_yaml_profile(tb, out_dir, logger)


if __name__ == '__main__':
    _create_profiles(sys.argv[1])

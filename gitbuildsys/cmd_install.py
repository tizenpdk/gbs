import os
import re
import subprocess
import fnmatch

from gitbuildsys.errors import GbsError, CmdError
from gitbuildsys.conf import configmgr
from gitbuildsys.log import LOGGER as log

from gbp.rpm.git import GitRepositoryError, RpmGitRepository

SUPPORTEDARCHS = [
    'x86_64',
    'i586',
    'armv6l',
    'armv7hl',
    'armv7l',
    'aarch64',
    'mips',
    'mipsel',
    ]

def get_profile(args):
    """
    Get the build profile to be used
    """
    if args.profile:
        profile_name = args.profile if args.profile.startswith("profile.") \
                                    else "profile." + args.profile
        profile = configmgr.build_profile_by_name(profile_name)
    else:
        profile = configmgr.get_current_profile()
    return profile

def filter_rpms(rpms, debug):
    result = []
    for r in rpms:
        filename = os.path.basename(r)
        if filename.find('-devel-') != -1:
            continue
        if not debug:
            if filename.find('-debuginfo-') != -1 or filename.find('-debugsource-') != -1:
                continue
        result.append(r)
    return result

def install_perform(directory, rpms, force, nodeps, method):
    #check for attached devices
    is_sdb = False
    if method == 'auto':
        if len(subprocess.Popen(['sdb', 'devices'], stdout = subprocess.PIPE).stdout.read().split('\n')) > 2:
            is_sdb = True
    elif method == 'sdb':
        is_sdb = True

    if is_sdb:
        log.info('Using sdb for installation')
        log.info('Running: sdb root on...')
        subprocess.Popen(['sdb', 'root', 'on']).wait()
    else:
        log.info('Using ssh for installation')

    idir = '/tmp/'

    #copy and install rpms
    for rpm in rpms:
        log.info('Uploading... %s' % rpm)
        filename = os.path.join(directory, rpm)
        args1 = []
        if is_sdb:
            args1 = ['sdb', 'push', filename, '%s/%s' % (idir, os.path.basename(filename))]
        else:
            args1 = ['scp', filename, 'target:%s' % idir]
        code_c = subprocess.Popen(args1).wait()
        if code_c:
            raise CmdError('Command failed: %s' % ' '.join(args1))

    args2 = []
    if is_sdb:
        args2 = ['sdb', 'shell', 'rpm', '-Uvh']
    else:
        args2 = ['ssh', 'target', 'rpm', '-Uvh']
    if force:
        args2.append('--force')
    if nodeps:
        args2.append('--nodeps')
    args2.append('%s/*.rpm' % idir)

    log.info('Installing...');
    code_i = subprocess.Popen(args2).wait()
    if code_i:
        raise CmdError('Command failed: %s' % ' '.join(args2))

    log.info('Cleaning up rpms...');
    for rpm in rpms:
        if is_sdb:
            args3 = ['sdb', 'shell', 'rm', '%s' % os.path.join(idir, os.path.basename(rpm))]
        else:
            args3 = ['ssh', 'target', 'rm', '%s' % os.path.join(idir, os.path.basename(rpm))]
        code_r = subprocess.Popen(args3).wait()
        if code_r:
            raise CmdError('Command failed: %s' % ' '.join(args3))

def main(args):
    """gbs install entry point."""

    hostarch = os.uname()[4]
    if args.arch:
        buildarch = args.arch
    else:
        buildarch = hostarch
        log.info('No arch specified, using system arch: %s' % hostarch)

    if not buildarch in SUPPORTEDARCHS:
        raise GbsError('arch %s not supported, supported archs are: %s ' % \
                       (buildarch, ','.join(SUPPORTEDARCHS)))

    profile = get_profile(args)
    if args.buildroot:
        build_root = args.buildroot
    elif profile.buildroot:
        build_root = profile.buildroot
    else:
        build_root = configmgr.get('buildroot', 'general')
    build_root = os.path.expanduser(build_root)
    # transform variables from shell to python convention ${xxx} -> %(xxx)s
    build_root = re.sub(r'\$\{([^}]+)\}', r'%(\1)s', build_root)
    sanitized_profile_name = re.sub("[^a-zA-Z0-9:._-]", "_", profile.name)
    build_root = build_root % {'profile': sanitized_profile_name}

    rpms_root = '%s/local/repos/%s/%s/RPMS' % (build_root, ".".join(sanitized_profile_name.split('.')[1:]), buildarch)
    build_root_dir = '%s/local/BUILD-ROOTS/scratch.%s.0/home/abuild/rpmbuild/RPMS' % (build_root, buildarch)
    rpms = []

    # list rpms
    if args.all:
        log.info("Proceeding all built rpms...")
        rpms = map(lambda x: os.path.join(rpms_root, x), os.listdir(rpms_root))
    else:
        log.info("Proceeding built rpms from latest built...")
        names = []
        for _, _, flist in os.walk(build_root_dir):
            for filename in flist:
                if fnmatch.fnmatch(filename, "*.rpm"):
                    names.append(filename)
        for dirname, _, flist in os.walk(rpms_root):
            for filename in flist:
                if filename in names:
                    rpms.append(os.path.join(dirname, filename))

    if not rpms:
        raise GbsError("No rpms found.")

    # filter rpms
    rpms = filter_rpms(rpms, args.debug)

    if not rpms:
        raise GbsError("No rpms selected.")

    # install rpms
    install_perform(dir, rpms, args.force, args.nodeps, args.method)
# standard library
import os
from shutil import rmtree
from tempfile import mkdtemp

# fabric
from fabric.api import cd
from fabric.api import env
from fabric.api import run
from fabric.api import sudo
from fabric.api import task
from fabric.colors import green
from fabric.context_managers import shell_env
from fabric.contrib.files import append
from fabric.tasks import execute

# fabtools
from fabtools import deb
from fabtools import group
from fabtools import user
from fabtools.files import upload_template

# utils
from fabfile import utils


ROOT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TEMPLATES_FOLDER = os.path.join(ROOT_FOLDER, 'templates/nix/')
PROFILE_SUFFIX = """
if [ "$USER" != root -a -e /nix/var/nix/daemon-socket/socket ]; then
export NIX_REMOTE=daemon
else
unset NIX_REMOTE
fi
"""

# See (http://hydra.nixos.org/job/nix/maintenance/release#tabs-constituents)
NIX_BUILDS_URL = "https://hydra.nixos.org/build/{build}/download/1/nix_{version}_amd64.deb"
NIX_BUILDS = {'trusty': {'build': 33897733,
                         'version': '1.11.2-1'},
              'xenial': {'build': 36401064,
                         'version': '1.11.2-1'}}
NIX_DEPS = {'trusty': (('libdbi-perl', None),
                       ('libdbd-sqlite3-perl', None),
                       ('libwww-curl-perl', None),
                       ('libnspr4-dev', None),
                       ('libnss3-nssdb', '2:3.21-0ubuntu0.14.04.2'),
                       ('libnss3', None),
                       ('libnss3-dev', None),
                       ('libcurl3-nss', None),
                       ('libcurl4-nss-dev', None)),
            'xenial': (('libdbi-perl', None),
                       ('libdbd-sqlite3-perl', None),
                       ('libsodium18', None),
                       ('libwww-curl-perl', None),
                       ('libcurl3-nss', None),
                       ('libcurl4-nss-dev', None))}


@task
def install_deps():
    # update apt index
    deb.update_index(quiet=False)

    # obtain the LSB codename
    codename = utils.deb.get_release_info().codename

    packages = NIX_DEPS[codename]
    for package, version in packages:
        deb.install(package, version)


@task
def user_setup():
    # Setup current user
    # You need to do this to enable Nix for a particular user
    current_user = env.user
    with shell_env(NIX_REMOTE='daemon'):
        run("mkdir -m 0755 -p /nix/var/nix/gcroots/per-user/{}".format(current_user))
        run("nix-env --switch-profile /nix/var/nix/profiles/per-user/{}/default".format(current_user))
        run('nix-channel --add https://nixos.org/channels/nixpkgs-unstable')
        run('nix-channel --update')


@task
def install():
    """ Installs Nix"""
    # Install the Nix package

    if not deb.is_installed('nix'):
        execute('nix.install_deps')

        # obtain the LSB codename
        codename = utils.deb.get_release_info().codename

        url = NIX_BUILDS_URL.format(**NIX_BUILDS[codename])

        tmp_dir = mkdtemp()

        with cd(tmp_dir):
            print(green('Downloading Nix 1.11.2'))
            run("wget '{}'".format(url))
            print(green('Installing Nix'))
            sudo('dpkg --unpack *.deb')
            deb.install('nix')
        rmtree(tmp_dir)

        # Create Nix build user accounts
        grp = 'nixbld'
        if not group.exists(grp):
            group.create(grp)

            for n in range(10):
                usr = "nixbld{}".format(n)
                if not user.exists(usr):
                    user.create(usr,
                                comment="Nix build user {}".format(n),
                                group=grp,
                                extra_groups=[grp],
                                system=True,
                                shell='/bin/false')

        sudo('mkdir -p /etc/nix')
        sudo('mkdir -p /nix/store')
        sudo('chown root.nixbld /nix/store')
        sudo('chmod 1775 /nix/store')
        sudo('mkdir -p -m 1777 /nix/var/nix/gcroots/per-user')
        sudo('mkdir -p -m 1777 /nix/var/nix/profiles/per-user')

        # Configure nix-daemon
        init_path = '/etc/init.d/'
        upload_template(os.path.join(TEMPLATES_FOLDER,
                                     'nix-daemon'),
                        init_path,
                        backup=False,
                        mode=0o755,
                        use_sudo=True)
        sudo('update-rc.d nix-daemon defaults')
        green('Starting nix-daemon')
        sudo('/etc/init.d/nix-daemon start')

        # Setup profile
        nix_profile = '/etc/profile.d/nix.sh'
        append(nix_profile,
               PROFILE_SUFFIX,
               use_sudo=True)

        sudo('service nix-daemon restart')

        # Setup Nix for current user
        execute('nix.user_setup')

        green('Done. Remember to log out and back in before using Nix.')

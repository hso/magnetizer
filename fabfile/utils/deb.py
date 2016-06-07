from collections import namedtuple
from fabric.api import run
from fabric.api import sudo
from fabtools.deb import install as deb_install
from fabtools.deb import is_installed


def install(package, upgrade=False):
    """
    Helper method to install a deb package.

    If the package is already installed and the parameter 'upgrade' is True,
    then it will be upgraded if possible.

    """
    if not is_installed(package):
        deb_install(package)

    if upgrade:
        cmd = 'apt-get install --only-upgrade {}'.format(package)
        sudo(cmd)


def get_release_info():
    """
    Helper method to query release info on Debian-based systems.

    Returns a tuple with
    """
    ReleaseInfo = namedtuple('ReleaseInfo', ['id', 'release', 'codename'])
    data = run('lsb_release --id --release --codename --short').split("\r\n")
    return ReleaseInfo(*data)

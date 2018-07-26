#!/cvmfs/soft.computecanada.ca/custom/python/envs/avail_wheels/bin/python3

import sys
import os
import glob
import re
import argparse
import fnmatch
import operator
from tabulate import tabulate
from distutils.version import LooseVersion

CURRENT_ARCHITECTURE = os.environ.get("RSNT_ARCH")
AVAILABLE_ARCHITECTURES = ['avx', 'avx2', 'sse3', 'generic']
ARCHITECTURES = ['generic', CURRENT_ARCHITECTURE]

AVAILABLE_PYTHONS = ["2.7", "3.5", "3.6", "3.7"]
CURRENT_PYTHON = os.environ.get("EBVERSIONPYTHON")
COMPATIBLE_PYTHON = {"2.7": ["py2.py3", "py2", "cp27"],
                     "3.5": ["py2.py3", "py3", "cp35"],
                     "3.6": ["py2.py3", "py3", "cp36"],
                     "3.7": ["py2.py3", "py3", "cp37"]}

WHEELHOUSE = "/cvmfs/soft.computecanada.ca/custom/python/wheelhouse"

AVAILABLE_HEADERS = ['name', 'version', 'build', 'python', 'abi', 'platform', 'arch']
HEADERS = ['name', 'version', 'build', 'python', 'arch']


class Wheel():
    """
    The representation of a wheel and its tags.
    """

    # The wheel filename is {arch}/{distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl.
    # The version can be numeric, alpha or alphanum or a combinaison.
    WHEEL_RE = re.compile(r"(?P<arch>\w+)/(?P<name>[\w.]+)-(?P<version>(?:[\w\.]+)?)(?:[\+-](?P<build>\w+))*?-(?P<python>[\w\.]+)-(?P<abi>\w+)-(?P<platform>\w+)")

    filename, arch, name, version, build, python, abi, platform = "", "", "", "", "", "", "", ""

    def __init__(self, filename, parse=True, **kwargs):
        self.filename = filename
        self.__dict__.update(kwargs)

        if parse:
            self.parse_tags(filename)

    def parse_tags(self, wheel):
        """
        Parse and set wheel tags.
        The wheel filename is {arch}/{distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl.
        """
        m = self.WHEEL_RE.match(wheel)
        if m:
            self.arch = m.group('arch')
            self.name = m.group('name')
            self.version = m.group('version')
            self.build = m.group('build')
            self.python = m.group('python')
            self.abi = m.group('abi')
            self.platform = m.group('platform')
        else:
            raise Exception(f"Could not get tags for : {wheel}")

    def loose_version(self):
        return LooseVersion(self.version)

    def __str__(self):
        return self.filename

    def __eq__(self, other):
        return isinstance(other, Wheel) and self.__dict__ == other.__dict__


def get_wheels(path, archs, name, version, pythons, latest=True):
    """
    Glob the full list of wheels in the wheelhouse on CVMFS.
    Can also be filterd on arch, name, version or python.
    Return a dict of wheel name and list of tags.
    """
    wheels = {}
    rex = re.compile(fnmatch.translate(f"{name}*{version}*.whl"), re.IGNORECASE)

    for arch in archs:
        for _, _, files in os.walk(f"{path}/{arch}"):
            for file in files:
                if re.match(rex, file):
                    wheel = Wheel(f"{arch}/{file}")
                    for p in pythons:  # Filter the wheels with available pythons version.
                        if wheel.python in COMPATIBLE_PYTHON[p]:
                            if wheel.name in wheels:
                                wheels[wheel.name].append(wheel)
                            else:
                                wheels[wheel.name] = [wheel]
                            break  # Exit pythons loop

    # Filter versions
    return latest_versions(wheels) if latest else wheels


def latest_versions(wheels):
    """
    Returns only the latest version of each wheel.
    """
    latests = {}

    for wheel_name, wheel_list in wheels.items():
        wheel_list.sort(key=operator.methodcaller('loose_version'), reverse=True)
        latests[wheel_name] = []
        latest = wheel_list[0].loose_version()

        for wheel in wheel_list:
            if latest == wheel.loose_version():
                latests[wheel_name].append(wheel)
            else:
                break

    return latests


def sort(wheels, columns):
    """
    Transforms dict of wheels to a list of lists
    where the columns are the wheel tags.
    """
    ret = []

    # Sort in-place, by name insensitively asc, then by version desc, then by arch desc, then by python desc
    # Since the sort is stable and Timsort can benefit from previous sort, this is fast.
    wheel_names = sorted(wheels.keys(), key=lambda s: s.casefold())
    for wheel_name in wheel_names:
        wheel_list = wheels[wheel_name]
        wheel_list.sort(key=operator.attrgetter('python'), reverse=True)
        wheel_list.sort(key=operator.attrgetter('arch'), reverse=True)
        wheel_list.sort(key=operator.methodcaller('loose_version'), reverse=True)

        for wheel in wheel_list:
            ret.append([getattr(wheel, column) for column in columns])

    return ret


def create_argparser():
    """
    Returns an arguments parser for `avail_wheels` command.
    Note : sys.argv is not parsed yet, must call `.parse_args()`.
    """
    parser = argparse.ArgumentParser(description="List available wheels patterns from the wheelhouse.")

    version_group = parser.add_mutually_exclusive_group()
    version_group.add_argument("-v", "--version", default="", help="Specify the version to look for.")
    version_group.add_argument("--all_versions", action='store_true', help="Show all versions of each wheel.")

    parser.add_argument("-a", "--arch", choices=AVAILABLE_ARCHITECTURES, nargs='+', default=ARCHITECTURES, help="Specify the architecture to look for.")
    parser.add_argument("-p", "--python", choices=AVAILABLE_PYTHONS, nargs='+', default=[CURRENT_PYTHON[:3]] if CURRENT_PYTHON else AVAILABLE_PYTHONS, help="Specify the python versions to look for.")
    parser.add_argument("-n", "--name", default="", help="Specify the name to look for (case insensitive).")
    parser.add_argument("--house", type=str, default=WHEELHOUSE, help="Specify the directory to walk.")

    display_group = parser.add_mutually_exclusive_group()
    display_group.add_argument("--raw", action='store_true', help="Print raw files names.")
    display_group.add_argument("--mediawiki", action='store_true', help="Print a mediawiki table.")
    display_group.add_argument("--column", choices=AVAILABLE_HEADERS, nargs='+', default=HEADERS, help="Specify and order the columns to display.")

    return parser


def main():
    args = create_argparser().parse_args()
    wheels = get_wheels(path=args.house, archs=args.arch, name=args.name, version=args.version, pythons=args.python, latest=not args.all_versions)

    if args.raw:
        for wheel_list in wheels.values():
            print(*wheel_list, sep='\n')
    else:
        wheels = sort(wheels, args.column)
        print(tabulate(wheels, headers=args.column, tablefmt="mediawiki" if args.mediawiki else "simple"))


if __name__ == "__main__":
    main()

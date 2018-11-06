import datetime
import gzip
import logging
import os
import re

logger = logging.getLogger(__name__)

BASE_DIR = '/var/log/apt/'
PACKAGE_FORMAT = re.compile('(\S+):(\S+) \(([^\(\)]*)\)')
ACTIONS = ('Install', 'Upgrade', 'Downgrade', 'Remove', 'Reinstall', 'Purge')


def _parse_date(date_string):
    return datetime.datetime.strptime(date_string, '%Y-%m-%d  %H:%M:%S')


class Package(object):

    def __init__(self, name, architecture, version, old_version, automatic):
        self.name = name
        self.architecture = architecture
        self.version = version
        self.old_version = old_version
        self.automatic = automatic

    def __str__(self):
        return "{}:{} ({})".format(self.name, self.architecture, self.version)

    def __repr__(self):
        return "Package({}, {}, {})".format(self.name, self.architecture, self.version)

def _parse_package(name, architecture, version, action):
    if action == 'Install':
        automatic = version.endswith(', automatic')
        if automatic:
            version = version[:-11]
    else:
        automatic = None
    if action == 'Upgrade':
        old_version, version = version.split(', ')
    else:
        old_version = None
    return Package(name, architecture, version, old_version, automatic)

def _parse_packages(raw_packages, action):
    l = len(raw_packages)
    pos = 0
    packages = []
    while pos < l:
        m = PACKAGE_FORMAT.match(raw_packages, pos)
        assert m, 'Malformed log in packages list \'{}\''.format(raw_packages)
        assert m.start() == pos, 'Malformed log in packages list \'{}\''.format(raw_packages)
        packages.append(_parse_package(*m.groups(), action))
        pos += len(m.group()) + 2
    return packages


class AptHistoryEntry(object):

    def __init__(self, raw_data):
        self.start_date = _parse_date(raw_data.pop('Start-Date'))
        self.end_date = _parse_date(raw_data.pop('End-Date')) if 'End-Date' in raw_data else None
        self.command = raw_data.pop('Commandline')
        self.requested_by = raw_data.pop('Requested-By', None)
        self.error = raw_data.pop('Error', None)
        self.actions = { action: _parse_packages(raw_data.pop(action), action) for action in ACTIONS if action in raw_data }
        assert not raw_data, 'Malformed log: Unknown entries: {}'.format(', '.join(raw_data.keys()))

    def get_package_action(self, name, architecture=None, version=None):
        for action, packages in self.actions.items():
            for package in packages:
                if package.name == name and (architecture is None or package.architecture == architecture) and (version is None or package.version == version):
                    return action, package
        return None, None


class AptHistory(object):

    def __init__(self, log_dir=BASE_DIR):
        self.log_dir = log_dir
        self.entries = sorted(map(AptHistoryEntry, self._parse_logs()), key=lambda entry:entry.start_date)

    def _parse_log(self, log_fh):
        entry = {}
        for line in log_fh:
            line = line.decode('utf8').rstrip()
            if line:
                key, value = line.split(': ', 1)
                entry[key] = value
            else:
                if entry:
                    yield entry
                entry = {}
        if entry is not None:
            if entry:
                yield entry
    
    def _parse_logs(self):
        for f in os.listdir(self.log_dir):
            if f.startswith('history.log'):
                with (gzip.open if f.endswith('.gz') else open)(os.path.join(self.log_dir, f), 'rb') as f:
                    yield from self._parse_log(f)

    def find_package_actions(self, name, architecture=None, version=None):
        for entry in self.entries:
            action, package = entry.get_package_action(name, architecture, version)
            if action is not None:
                yield (entry, action, package)

import dateparser
import datetime
import gzip
import itertools
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

    def __init__(self, name, architecture, version, old_version):
        self.name = name
        self.architecture = architecture
        self.version = version
        self.old_version = old_version

    def __str__(self):
        return "{}:{} ({})".format(self.name, self.architecture, self.version)

    def __repr__(self):
        return "Package({}, {}, {})".format(self.name, self.architecture, self.version)

def _parse_package_list(raw_packages, action):
    l = len(raw_packages)
    pos = 0
    packages = []
    while pos < l:
        m = PACKAGE_FORMAT.match(raw_packages, pos)
        assert m, 'Malformed log in packages list \'{}\''.format(raw_packages)
        assert m.start() == pos, 'Malformed log in packages list \'{}\''.format(raw_packages)
        name, architecture, version = m.groups()
        if action == 'Install' and version.endswith(', automatic'):
            target_action = 'Auto-Install'
            version = version[:-11]
        else:
            target_action = action
        if action == 'Upgrade':
            old_version, version = version.split(', ')
        else:
            old_version = None
        yield target_action, Package(name, architecture, version, old_version)
        pos += len(m.group()) + 2

class AptHistoryEntry(object):

    def __init__(self, raw_data):
        self.id = None
        self.start_date = _parse_date(raw_data.pop('Start-Date')) if 'Start-Date' in raw_data else None
        self.end_date = _parse_date(raw_data.pop('End-Date')) if 'End-Date' in raw_data else None
        if self.start_date is not None and self.end_date is not None:
            self.duration = self.end_date - self.start_date
        else:
            self.duration = None
        self.command = raw_data.pop('Commandline')
        self.requested_by = raw_data.pop('Requested-By', None)
        self.error = raw_data.pop('Error', None)
        self.actions = {}
        for action, packages in itertools.chain.from_iterable(_parse_package_list(raw_data.pop(action), action) for action in ACTIONS if action in raw_data):
            self.actions.setdefault(action, []).append(packages)
        assert not raw_data, 'Malformed log: Unknown entries: {}'.format(', '.join(raw_data.keys()))

    def is_before(self, date):
        return self.end_date is not None and self.end_date < date

    def is_after(self, date):
        return self.start_date is not None and self.start_date > date

    def get_packages(self, action, name, architecture=None, version=None, regex=False):
        for package in self.actions.get(action, []):
            if (regex and re.match(name, package.name)) or (not regex and package.name == name):
                if (architecture is None or package.architecture == architecture) and (version is None or package.version == version):
                    yield package

    def get_package_actions(self, name, architecture=None, version=None, regex=False):
        actions = {}
        for action, packages in self.actions.items():
            packages = list(self.get_packages(action, name, architecture, version, regex))
            if packages:
                actions[action] = packages
        return actions


class AptHistory(object):

    def __init__(self, log_dir=BASE_DIR):
        self.log_dir = log_dir
        self.entries = sorted(map(AptHistoryEntry, self._parse_logs()), key=lambda entry:entry.start_date)

        for n, entry in enumerate(self.entries, 1):
            entry.id = n

    def get_entries(self, min_date=None, max_date=None):
        min_date = datetime.datetime.min if min_date is None else min_date if isinstance(min_date, datetime.datetime) else dateparser.parse(min_date)
        max_date = datetime.datetime.max if max_date is None else max_date if isinstance(max_date, datetime.datetime) else dateparser.parse(max_date)
        return filter(lambda entry: entry.is_after(min_date) and entry.is_before(max_date), self.entries)

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

    def find_package_actions(self, name, architecture=None, version=None, regex=False):
        for entry in self.entries:
            actions = entry.get_package_actions(name, architecture, version, regex)
            if actions:
                yield (entry, actions)

    def __getitem__(self, id):
        return self.entries[id-1]

    def __iter__(self):
        return iter(self.entries)

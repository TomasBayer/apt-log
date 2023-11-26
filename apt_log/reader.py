import gzip
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Iterator, Pattern, TextIO

from dataclass_builder import dataclass_builder

from apt_log.log import AptLog, AptLogEntry, ChangedPackage, PackageAction


@dataclass
class AptLogReader:
    LOG_ENTRY_FORMAT: Final[Pattern] = re.compile(r'(^\n|\n\n)(.+?)(?=\n\n|\n$)', re.DOTALL)
    PACKAGE_FORMAT: Final[Pattern] = re.compile(r'(\S+):(\S+) \(([^()]*)\)')

    def read_log_entries(self, file: str | TextIO) -> Iterator[str]:
        for m in self.LOG_ENTRY_FORMAT.finditer(file if isinstance(file, str) else file.read()):
            yield m.group(2)

    def parse_package_list(self, raw_packages: str, action: PackageAction) -> Iterator[ChangedPackage]:
        for m in self.PACKAGE_FORMAT.finditer(raw_packages):
            name, architecture, version = m.groups()

            builder = dataclass_builder(ChangedPackage)(
                name=name,
                architecture=architecture,
                version=version,
                action=action,
            )

            if builder.version.endswith(', automatic'):
                builder.version = builder.version[:-11]
                builder.is_automatic = True

            if ', ' in builder.version:
                builder.previous_version, builder.version = builder.version.split(', ')

            yield builder.build()

    def parse_date(self, date_string: str) -> datetime:
        return datetime.strptime(date_string, '%Y-%m-%d  %H:%M:%S')

    def parse_log_entry(self, log_entry: str) -> AptLogEntry:
        entry_builder = dataclass_builder(AptLogEntry)(changed_packages_by_action={})

        for line in log_entry.splitlines():
            key, value = line.split(': ', 1)

            if key == 'Start-Date':
                entry_builder.start_date = self.parse_date(value)
            elif key == 'End-Date':
                entry_builder.end_date = self.parse_date(value)
            elif key == 'Commandline':
                entry_builder.command_line = value
            elif key == 'Requested-By':
                entry_builder.requested_by = value
            elif key == 'Error':
                entry_builder.error = value
            else:
                try:
                    action = PackageAction[key.upper()]
                    entry_builder.changed_packages_by_action[action] = list(self.parse_package_list(value, action))
                except KeyError as err:
                    raise ValueError(f"Malformed log: Unknown entry: {key}") from err

            for action, changed_packages in entry_builder.changed_packages_by_action.items():
                entry_builder.changed_packages_by_action[action] = sorted(
                    changed_packages, key=lambda package: (package.is_automatic, package.name),
                )

        return entry_builder.build()

    def parse_log_files(self, *log_files: str | TextIO) -> Iterator[AptLogEntry]:
        for log_file in log_files:
            for log_entry in self.read_log_entries(log_file):
                yield self.parse_log_entry(log_entry)

    def build_log(self, *log_files: str | TextIO) -> AptLog:
        return AptLog(self.parse_log_files(*log_files))


LOG_DIR: Path = Path('/var/log/apt/')
LOG_FILE_GLOB_PATTERN: str = 'history.log*'


def get_system_log_files() -> Iterator[TextIO]:
    for f in LOG_DIR.glob(LOG_FILE_GLOB_PATTERN):
        file_open = gzip.open if f.suffix == '.gz' else open

        with file_open(LOG_DIR / f, 'rt') as file:
            yield file.read()


def build_system_apt_log() -> AptLog:
    return AptLogReader().build_log(*get_system_log_files())

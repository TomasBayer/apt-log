import enum
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from fnmatch import fnmatch
from typing import Collection, Iterable, Iterator


class PackageAction(enum.StrEnum):
    INSTALL = "Install"
    UPGRADE = "Upgrade"
    DOWNGRADE = "Downgrade"
    REMOVE = "Remove"
    REINSTALL = "Reinstall"
    PURGE = "Purge"


@dataclass
class ChangedPackage:
    name: str
    architecture: str
    version: str

    action: PackageAction

    previous_version: str | None = None
    is_automatic: bool = False


@dataclass
class AptLogEntry:
    id: int | None = None

    changed_packages_by_action: dict[PackageAction, list[ChangedPackage]] = field(default_factory=dict)

    start_date: datetime | None = None
    end_date: datetime | None = None

    command_line: str | None = None
    requested_by: str | None = None
    error: str | None = None

    def is_before(self, date: datetime) -> bool:
        return self.end_date is not None and self.end_date < date

    def is_after(self, date: datetime) -> bool:
        return self.start_date is not None and self.start_date > date

    @property
    def duration(self) -> timedelta | None:
        if self.start_date is None or self.end_date is None:
            return None
        else:
            return self.end_date - self.start_date

    def filter(
            self,
            package_name: str | None = None,
            architecture: str | None = None,
            version: str | None = None,
            actions: Collection[PackageAction] | None = None,
    ) -> 'AptLogEntry':
        changed_packages_by_action = {}

        for action, changed_packages in self.changed_packages_by_action.items():
            if actions is None or action in actions:
                filtered_packages = [
                    package for package in changed_packages
                    if all((
                        package_name is None or fnmatch(package.name, package_name),
                        architecture is None or architecture == package.architecture,
                        version is None or version == package.version,
                    ))
                ]
                if filtered_packages:
                    changed_packages_by_action[action] = filtered_packages

        return replace(self, changed_packages_by_action=changed_packages_by_action)

    def has_changed_packages(self) -> bool:
        return bool(self.changed_packages_by_action)

    def has_version_changes(self) -> bool:
        return any(
            action in self.changed_packages_by_action for action in (PackageAction.UPGRADE, PackageAction.DOWNGRADE)
        )


@dataclass
class InvalidAptLogEntryIDError(Exception):
    wrong_entry_id: int

    def __str__(self):
        return f"Invalid log entry: {self.wrong_entry_id}"


class AptLog:
    entries: list[AptLogEntry]

    def __init__(self, entries: Iterable[AptLogEntry]):
        # Sort entries chronologically
        entries = sorted(entries, key=lambda entry: entry.start_date)

        # Assign entry IDs in ascending chronological order starting with 1
        for n, entry in enumerate(entries, 1):
            entry.id = n

        self.entries = entries

    def get_entries(
            self,
            start_date: datetime | None = None,
            end_date: datetime | None = None,
            package_name: str | None = None,
            architecture: str | None = None,
            version: str | None = None,
            actions: Collection[PackageAction] | None = None,
    ) -> Iterator[AptLogEntry]:
        for entry in self.entries:
            if start_date is not None and entry.is_before(start_date):
                continue

            if end_date is not None and entry.is_after(end_date):
                continue

            filtered_entry = entry.filter(
                package_name=package_name,
                architecture=architecture,
                version=version,
                actions=actions,
            )

            if filtered_entry.has_changed_packages():
                yield filtered_entry

    def get_entry_by_id(self, entry_id: int) -> AptLogEntry:
        try:
            return self.entries[entry_id - 1]
        except IndexError as err:
            raise InvalidAptLogEntryIDError(entry_id) from err

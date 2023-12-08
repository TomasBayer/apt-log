from datetime import datetime

import pytest

from apt_log.log import AptLog, AptLogEntry, ChangedPackage, InvalidAptLogEntryIDError, PackageAction


@pytest.fixture
def sample_log_entries() -> list[AptLogEntry]:
    return [
        AptLogEntry(
            start_date=datetime(2023, 1, 1, 10, 0, 0),
            end_date=datetime(2023, 1, 1, 10, 15, 0),
            command_line="apt-get install example-package",
            requested_by="user",
            changed_packages_by_action={PackageAction.INSTALL: [ChangedPackage(
                name="example-package",
                architecture="amd64",
                version="1.0.0",
                action=PackageAction.INSTALL,
            )]},
        ),
        AptLogEntry(
            start_date=datetime(2023, 1, 1, 10, 25, 0),
            end_date=datetime(2023, 1, 1, 10, 30, 0),
            command_line="apt-get upgrade",
            requested_by="another-user",
            changed_packages_by_action={PackageAction.UPGRADE: [ChangedPackage(
                name="upgraded-package",
                architecture="amd64",
                version="2.0.0",
                previous_version="1.0.0",
                action=PackageAction.UPGRADE,
            )]},
        )]


class TestAptLog:

    def test_init(self, sample_log_entries):
        apt_log = AptLog(sample_log_entries)

        assert len(apt_log.entries) == 2
        assert apt_log.entries[0].id == 1
        assert apt_log.entries[1].id == 2

    def test_get_entries(self, sample_log_entries):
        apt_log = AptLog(sample_log_entries)

        entries = list(apt_log.get_entries(start_date=datetime(2023, 1, 1, 10, 10, 0)))
        assert len(entries) == 2

        entries = list(apt_log.get_entries(start_date=datetime(2023, 1, 1, 10, 20, 0)))
        assert len(entries) == 1

        entries = list(apt_log.get_entries(package_name='example-package'))
        assert len(entries) == 1

        entries = list(apt_log.get_entries(package_name='another-package'))
        assert len(entries) == 0

        entries = list(apt_log.get_entries(package_name='*-package'))
        assert len(entries) == 2

        entries = list(apt_log.get_entries(package_name='*-p'))
        assert len(entries) == 0

    def test_apt_log_get_entry_by_id(self, sample_log_entries):
        apt_log = AptLog(sample_log_entries)

        entry = apt_log.get_entry_by_id(1)
        assert isinstance(entry, AptLogEntry)
        assert entry.id == 1

    def test_apt_log_get_entry_by_invalid_id(self, sample_log_entries):
        apt_log = AptLog(sample_log_entries)

        with pytest.raises(InvalidAptLogEntryIDError):
            apt_log.get_entry_by_id(3)

    def test_apt_log_get_last_entry(self, sample_log_entries):
        apt_log = AptLog(sample_log_entries)

        last_entry = apt_log.get_last_entry()
        assert isinstance(last_entry, AptLogEntry)
        assert last_entry.id == 2

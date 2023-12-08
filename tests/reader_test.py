from datetime import datetime, timedelta

import pytest

from apt_log.log import AptLog, AptLogEntry, PackageAction
from apt_log.reader import AptLogReader


@pytest.fixture
def sample_package_list() -> str:
    return "example-package:amd64 (1.0.0), auto-package:i386 (1.0.0, automatic), upgraded-package:arm64 (1.0.0, 2.0.0)"


@pytest.fixture
def sample_log_entry(sample_package_list) -> str:
    return (f"Start-Date: 2023-01-01 10:00:00\n"
            f"End-Date: 2023-01-01 10:15:00\n"
            f"Commandline: apt-get install example-package\n"
            f"Requested-By: user\n"
            f"Install: {sample_package_list}")


@pytest.fixture
def sample_log_file(sample_log_entry) -> str:
    return f"\n{sample_log_entry}\n" * 3


class TestAptLogReader:

    def test_parse_date(self):
        parsed_date = AptLogReader().parse_date('2023-01-01 12:00:00')

        assert parsed_date == datetime(2023, 1, 1, 12, 0, 0)

    def test_parse_package_list(self, sample_package_list):
        packages = list(AptLogReader().parse_package_list(sample_package_list, action=PackageAction.INSTALL))

        assert len(packages) == 3

        assert packages[0].name == 'example-package'
        assert packages[0].architecture == 'amd64'
        assert packages[0].version == '1.0.0'
        assert packages[0].previous_version is None
        assert not packages[0].is_automatic
        assert packages[0].action == PackageAction.INSTALL

        assert packages[1].name == 'auto-package'
        assert packages[1].architecture == 'i386'
        assert packages[1].version == '1.0.0'
        assert packages[1].previous_version is None
        assert packages[1].is_automatic
        assert packages[1].action == PackageAction.INSTALL

        assert packages[2].name == 'upgraded-package'
        assert packages[2].architecture == 'arm64'
        assert packages[2].version == '2.0.0'
        assert packages[2].previous_version == '1.0.0'
        assert not packages[2].is_automatic
        assert packages[2].action == PackageAction.INSTALL

    def test_parse_log_entry(self, sample_log_entry):
        log_entry = AptLogReader().parse_log_entry(sample_log_entry)

        assert isinstance(log_entry, AptLogEntry)
        assert log_entry.start_date == datetime(2023, 1, 1, 10, 0, 0)
        assert log_entry.end_date == datetime(2023, 1, 1, 10, 15, 0)
        assert log_entry.duration == timedelta(minutes=15)
        assert log_entry.command_line == 'apt-get install example-package'
        assert log_entry.requested_by == 'user'
        assert log_entry.error is None
        assert log_entry.changed_packages_by_action.keys() == {PackageAction.INSTALL}
        assert len(log_entry.changed_packages_by_action[PackageAction.INSTALL]) == 3

    def test_read_log_entries(self, sample_log_file, sample_log_entry):
        log_entries = list(AptLogReader().read_log_entries(sample_log_file))

        assert len(log_entries) == 3
        assert log_entries[0] == sample_log_entry
        assert log_entries[1] == sample_log_entry
        assert log_entries[2] == sample_log_entry

    def test_parse_log_files(self, sample_log_file):
        log_entries = list(AptLogReader().parse_log_files(sample_log_file))

        assert len(log_entries) == 3
        assert isinstance(log_entries[0], AptLogEntry)
        assert isinstance(log_entries[1], AptLogEntry)
        assert isinstance(log_entries[2], AptLogEntry)

    def test_build_log(self, sample_log_file):
        log = AptLogReader().build_log(sample_log_file)
        assert isinstance(log, AptLog)
        assert len(log.entries) == 3

"""Tests for Utility Functions"""

import pytest
from pi_stream.hardware.background_process import BackgroundProcess
from pi_stream.hardware.util import force_exists, force_stop

NO_ARGS_COMMAND = "cat"

ARGS_COMMAND = "cat"
ARGS_ARG = "-t"
ARGS_ARGS = "-t -b"

INVALID_COMMAND = "nao"

INSTANT_COMMAND = "pwd"
INSTANT_ARGS = "-L"

FILTER = "ignore::pytest.PytestUnhandledThreadExceptionWarning"


class TestForceStop:
    """Tests for stopping a background process (forcefully)"""
    def test_started(self):
        """Force stop a started process"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.start()
        assert force_stop(ARGS_COMMAND)["success"]

    def test_instant(self):
        """Force stop a started process that ends instantly (e.g. ls)"""
        process = BackgroundProcess(INSTANT_COMMAND, INSTANT_ARGS)
        process.start()
        process.wait()  # wait for command to complete
        assert not force_stop(ARGS_COMMAND)["success"]


@pytest.mark.filterwarnings(FILTER)
class TestForceExists:
    """Tests for checking if a process exists by name"""
    def test_started(self):
        """Verify a started process with the name exists"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.start()
        assert force_exists(ARGS_COMMAND)["success"]
        process.stop()  # stop process for next test to succeed

    def test_stopped(self):
        """Verify a stopped process with the name does not exist"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        assert not force_exists(ARGS_COMMAND)["success"]

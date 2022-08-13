"""pytest unit tests for background_process.py"""
import pytest
import sh
from pi_stream.hardware.background_process import *

NO_ARGS_COMMAND = "cat"

ARGS_COMMAND = "cat"
ARGS_ARG = "-t"
ARGS_ARGS = "-t -b"

INVALID_COMMAND = "nao"

INSTANT_COMMAND = "pwd"
INSTANT_ARGS = "-L"

FILTER = "ignore::pytest.PytestUnhandledThreadExceptionWarning"


class TestConstructor:
    """Tests for the BackgroundProcess constructor"""
    def test_no_args(self):
        """Caling constructor with a command with no arguments"""
        BackgroundProcess(NO_ARGS_COMMAND)

    def test_one_args(self):
        """Calling constructor with a command with one argument"""
        args = ARGS_ARGS.split()
        BackgroundProcess(ARGS_COMMAND, args[0])

    def test_args(self):
        """Calling constructor with a command with more than one argument"""
        BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)

    def test_invalid(self):
        """Calling constructor with a nonexistant command"""
        with pytest.raises(sh.CommandNotFound):
            BackgroundProcess(INVALID_COMMAND)


class TestStart:
    """Tests for starting a background process"""
    def test_no_args(self):
        """Starting a process normally with no arguments"""
        process = BackgroundProcess(NO_ARGS_COMMAND)
        assert process.start()["code"] == ProcessErrorCode.SUCCESS

    def test_args(self):
        """Starting a process normally with arguments"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        assert process.start()["code"] == ProcessErrorCode.SUCCESS

    def test_stopped_restart(self):
        """Starting a process with the restart flag.
        Should be no different than a normal start in this case"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        assert process.start(restart=True)["code"] == ProcessErrorCode.SUCCESS

    def test_started(self):
        """Trying to start a process that is already started"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.start()
        assert process.start()["code"] == ProcessErrorCode.INVALID_STATE

    def test_started_restart(self):
        """Trying to start a process that is already started"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.start()
        code = process.start(restart=True)["code"]
        assert code == ProcessErrorCode.INVALID_STATE

    def test_restarting(self):
        """Trying to start a process that is already in a restarting process"""
        process = process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.start()
        process.state = ProcessState.RESTARTING  # manual set
        assert process.start()["code"] == ProcessErrorCode.IN_RESTART_PROCESS


@pytest.mark.filterwarnings(FILTER)
class TestStop:
    """Tests for stopping a background process"""
    def test_started(self):
        """Stop a started process"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.start()
        assert process.stop()["code"] == ProcessErrorCode.SUCCESS

    def test_stopped(self):
        """Try to stop an already stopped process"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.stop()
        assert process.stop()["code"] == ProcessErrorCode.INVALID_STATE

    def test_started_restart(self):
        """Initiate a restart process"""
        process = BackgroundProcess(ARGS_COMMAND, ARGS_ARGS)
        process.start()
        result = process.stop(restart=True)
        assert result["code"] == ProcessErrorCode.SUCCESS
        assert result["state"] == ProcessState.RESTARTING

    def test_instant(self):
        """Stop a started process that ends on its own ("instantly")
        (e.g. ls)"""
        process = BackgroundProcess(INSTANT_COMMAND, INSTANT_ARGS)
        process.start()
        process.wait()  # wait for command to complete
        assert process.stop()["code"] == ProcessErrorCode.STOPPED_SELF

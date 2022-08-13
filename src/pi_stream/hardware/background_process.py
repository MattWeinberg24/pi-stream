"""Controller for a background process such as janus or gstreamer"""

from enum import Enum
import signal
from loguru import logger
import sh


class ProcessErrorCode(str, Enum):
    """Error Codes"""
    SUCCESS = 'SUCCESS'
    INVALID_STATE = 'INVALID_STATE'  # operation attempted in invalid state

    # duplicate start attempted during restart process
    IN_RESTART_PROCESS = 'IN_RESTART_PROCESS'

    # stop attempted for a process that stopped on its own
    # (uncommon due to _done callback updating state)
    STOPPED_SELF = 'STOPPED_SELF'


class ProcessState(str, Enum):
    """Service State Labels"""
    STOPPED = 'STOPPED'
    STARTED = 'STARTED'
    STARTING = 'STARTING'
    STOPPING = 'STOPPING'
    RESTARTING = 'RESTARTING'


class BackgroundProcess:
    """Controller for a background process such as janus or gstreamer"""

    VALID_STATE_TRANSITIONS = [
        (ProcessState.STOPPED, ProcessState.STARTING),
        (ProcessState.STARTING, ProcessState.STARTED),
        (ProcessState.STARTED, ProcessState.STOPPING),
        (ProcessState.STOPPING, ProcessState.STOPPED),

        # case where stops on its own
        (ProcessState.STARTED, ProcessState.STOPPED),

        (ProcessState.STARTED, ProcessState.RESTARTING),  # restart part 1
        (ProcessState.RESTARTING, ProcessState.STARTED)   # restart part 2
    ]

    def __init__(self,
                 command_name: str,
                 arguments: str = "",
                 verbose: bool = False):
        self._name = command_name
        self._command = sh.Command(command_name)
        self._args = arguments.split()
        self._process = None
        self._state = ProcessState.STOPPED
        self._verbose = verbose

    @property
    def state(self):
        """service state"""
        return self._state

    @state.setter
    def state(self, new_state):
        transition = (self._state, new_state)
        if transition in self.VALID_STATE_TRANSITIONS:
            logger.info(f"{self._name}: {self._state} to {new_state}")
        else:
            logger.warning(f"\n{self._name}: {self._state} to {new_state}")
        self._state = new_state

    def start(self, arguments: str = None, restart: bool = False):
        """
        Starts process

        Args:
            restart (bool): true if part of a restart for a process
        """

        def output(data):
            """Callback for stdout from process"""
            if self._verbose:
                logger.debug(data)

        def done(cmd, success, exit_code):
            """Callback whenever a process exits"""
            logger.info(f"{self._name} is_alive:{self._process.is_alive()}")
            if success:
                logger.success(f"Stopped {self._name} (exit code {exit_code})")
                if self.state != ProcessState.RESTARTING:
                    self.state = ProcessState.STOPPED

        acceptable_states = [ProcessState.STOPPED, ProcessState.RESTARTING]

        if self.state not in acceptable_states:
            logger.warning(f"{self._name}: {self.state} (can't start)")
            return {
                "success": False,
                "process_code": ProcessErrorCode.INVALID_STATE.value,
                "process_state": self.state.value
            }

        # edge case where in RESTARTING state but not part of a restart process
        if self.state == ProcessState.RESTARTING and not restart:
            logger.warning(f"{self._name}: in restarting process")
            return {
                "success": False,
                "process_code": ProcessErrorCode.IN_RESTART_PROCESS.value,
                "process_state": self.state.value,
            }

        logger.info(f"Starting {self._name}...")

        if self.state != ProcessState.RESTARTING:
            self.state = ProcessState.STARTING

        # check if argument override
        if arguments is not None:
            # TODO: Done callback
            self._process = self._command(*(arguments.split()),
                                          _out=output,
                                          _bg=True, _bg_exc=True,
                                          _done=done)
        else:
            self._process = self._command(*(self._args),
                                          _out=output,
                                          _bg=True, _bg_exc=True,
                                          _done=done)

        logger.info(f"{self._name} PID:{self._process.pid}")
        logger.success(f"Started {self._name}")
        self.state = ProcessState.STARTED
        return {
            "success": True,
            "process_code": ProcessErrorCode.SUCCESS.value,
            "process_state": self.state.value
        }

    def stop(self, restart=False):
        """
        Stops process started with the start() function

        Args:
            restart (bool): true if part of a restart for a process
        """

        if self.state != ProcessState.STARTED:
            logger.warning(f"{self._name}: {self.state} (can't stop)")
            return {
                "success": False,
                "process_code": ProcessErrorCode.INVALID_STATE.value,
                "process_state": self.state.value
            }

        logger.info(f"Stopping {self._name}...")

        if restart:
            self.state = ProcessState.RESTARTING
        else:
            self.state = ProcessState.STOPPING

        try:
            self._process.signal(signal.SIGINT)
            logger.info(f"SIGINT sent to {self._name} (waiting for cleanup)")
            self._process.wait()
        except sh.SignalException as exc:
            # sometimes triggers because of the SIGINT
            logger.debug(exc)
        except sh.ErrorReturnCode as exc:
            # sometimes triggers because of the SIGINT
            logger.debug(exc.stderr.decode("utf-8"))
        except ProcessLookupError as exc:
            self.state = ProcessState.STOPPED
            logger.debug(exc)
            return {
                "success": False,
                "process_code": ProcessErrorCode.STOPPED_SELF.value,
                "process_state": self.state.value,
            }

        return {
            "success": True,
            "process_code": ProcessErrorCode.SUCCESS.value,
            "process_state": self.state.value
        }

    def status(self) -> dict:
        """Gets status of process"""
        if self._process is None:
            return {
                "name": self._name,
                "process_state": self.state.value,
            }
        return {
            "name": self._name,
            "process_state": self.state.value,
            "pid": self._process.pid,
            "is_alive": self._process.is_alive()
        }

    def wait(self):
        """calls wait() on the process (for testing)"""
        self._process.wait()

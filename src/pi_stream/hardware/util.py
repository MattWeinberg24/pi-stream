"""Utility Functions"""

import os

from loguru import logger
import sh


def force_stop(command_name: str):
    """Runs pkill with SIGINT on any process with this name on the device"""
    basename = os.path.basename(command_name)
    logger.info(f"Force-Stopping {basename} ({command_name})...")
    try:
        pkill = sh.Command("pkill")
        pkill("--signal", "SIGINT", basename)
    except sh.ErrorReturnCode as exc:
        logger.debug(exc)
        return {
            "success": False
        }

    logger.success(f"Force-Stopped {basename}")
    return {
        "success": True,
    }


def force_exists(command_name: str):
    """Runs pgrep, looking for any process with this name on the machine.
    Useful if there is a Janus process that the API is not keeping track of"""
    basename = os.path.basename(command_name)
    logger.info(f"Looking for process {basename} ({command_name})...")
    try:
        pgrep = sh.Command("pgrep")
        result = pgrep(basename)
        pid = result.stdout.decode("utf-8").strip()

        logger.warning(f"{basename} exists at PID:{pid}")
        return {
            "success": True,
            "pid": pid
        }
    except sh.ErrorReturnCode as exc:
        logger.debug(exc)
        logger.info(f"No {basename} process exists")
        return {
            "success": False
        }


def video_length(path: str) -> float:
    """Gets the length of a video in seconds

    Args:
        path (str): video path

    Returns:
        float: legnth in seconds
    """

    args = ["-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
            ]

    try:
        ffprobe = sh.Command("ffprobe")
        result = ffprobe(*(args))
        return float(result.stdout.decode("utf-8"))
    except sh.ErrorReturnCode as exc:
        logger.error(exc)
        return -1.0

#!/usr/bin/env python3

import subprocess
import sys
import typing
from arcaflow_plugin_sdk import plugin

# This now imports the new Annotated schemas
from canutils_schema import (
    CanplayerInput,
    CansendInput,
    SuccessOutput,
    ErrorOutput,
)


@plugin.step(
    id="player",
    name="Run canplayer",
    description="Replays a CAN log file to a CAN interface.",
    outputs={"success": SuccessOutput, "error": ErrorOutput},
)
def run_canplayer(
    params: CanplayerInput,
) -> typing.Tuple[str, typing.Union[SuccessOutput, ErrorOutput]]:
    cmd = ["canplayer", "-I", params.logfile]

    if params.verbose:
        cmd.append("-v")

    if params.infinite_loop:
        cmd.extend(["-l", "i"])
    elif params.loop_count > 1:
        cmd.extend(["-l", str(params.loop_count)])

    if params.interface:
        cmd.append(params.interface)

    print(cmd)

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return "success", SuccessOutput(process.stdout, process.stderr)
    except FileNotFoundError:
        return "error", ErrorOutput(1, "'canplayer' not found.")
    except subprocess.CalledProcessError as e:
        return "error", ErrorOutput(e.returncode, e.stderr)


@plugin.step(
    id="sender",
    name="Run cansend",
    description="Sends a single CAN frame to an interface.",
    outputs={"success": SuccessOutput, "error": ErrorOutput},
)
def run_cansend(
    params: CansendInput,
) -> typing.Tuple[str, typing.Union[SuccessOutput, ErrorOutput]]:
    cmd = ["cansend", params.interface, params.frame]
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return "success", SuccessOutput(process.stdout, process.stderr)
    except FileNotFoundError:
        return "error", ErrorOutput(1, "'cansend' not found.")
    except subprocess.CalledProcessError as e:
        return "error", ErrorOutput(e.returncode, e.stderr)


if __name__ == "__main__":
    sys.exit(
        plugin.run(
            plugin.build_schema(
                run_canplayer,
                run_cansend,
            )
        )
    )

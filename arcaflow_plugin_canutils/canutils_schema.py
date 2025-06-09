from dataclasses import dataclass
from typing import Annotated, List, Optional

from arcaflow_plugin_sdk import schema


@dataclass
class SuccessOutput:
    """
    This is the output data structure for a successful step execution.
    """

    stdout: Annotated[str, schema.name("Standard Output")]
    stderr: Annotated[str, schema.name("Standard Error")]


@dataclass
class ErrorOutput:
    """
    This is the output data structure in case of an error.
    """

    exit_code: Annotated[int, schema.name("Exit Code")]
    error: Annotated[str, schema.name("Error Message")]


@dataclass
class CanplayerInput:
    """
    Inputs for the canplayer step with explicit parameters.
    """

    logfile: Annotated[
        str,
        schema.name("Log File"),
        schema.description("Path to the CAN log file to be replayed."),
    ]
    interface: Annotated[
        Optional[str],
        schema.name("CAN Interface"),
        schema.description("The CAN interface to use (e.g., 'can0', 'vcan0')."),
    ] = None
    loop_count: Annotated[
        int,
        schema.min(1),
        schema.name("Loop Count"),
        schema.description(
            "Number of times to replay the log file. Set to 1 for a single run."
        ),
    ] = 1
    infinite_loop: Annotated[
        bool,
        schema.name("Infinite Loop"),
        schema.description(
            "Infinitely replay the log file. Overrides loop_count if true."
        ),
    ] = False
    verbose: Annotated[
        bool,
        schema.name("Verbose Output"),
        schema.description("Enable verbose output (-v) from canplayer."),
    ] = False


@dataclass
class CansendInput:
    """
    Inputs for the cansend step.
    """

    interface: Annotated[
        str,
        schema.name("CAN Interface"),
        schema.description("The CAN interface to use (e.g., 'can0', 'vcan0')."),
    ]
    frame: Annotated[
        str,
        schema.name("CAN Frame"),
        schema.description("The CAN frame to send, e.g., '123#112233FF'"),
    ]

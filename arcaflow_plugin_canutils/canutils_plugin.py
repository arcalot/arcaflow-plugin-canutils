#!/usr/bin/env python3

import subprocess
import sys
import time
import signal
import typing
from threading import Event
from arcaflow_plugin_sdk import plugin, predefined_schemas

# This now imports the new Annotated schemas
from canutils_schema import (
    CanplayerInput,
    CansendInput,
    SuccessOutput,
    ErrorOutput,
)


class CanplayerStep:
    exit = Event()
    finished_early = False

    @plugin.signal_handler(
        id=predefined_schemas.cancel_signal_schema.id,
        name=predefined_schemas.cancel_signal_schema.display.name,
        description=predefined_schemas.cancel_signal_schema.display.description,
        icon=predefined_schemas.cancel_signal_schema.display.icon,
    )
    def cancel_step(self, _input: predefined_schemas.cancelInput):
        # First, let it know that this is the reason it's exiting.
        self.finished_early = True
        # Now signal to exit.
        self.exit.set()

    @plugin.step_with_signals(
        id="player",
        name="Run canplayer",
        description="Replays a CAN log file to a CAN interface.",
        outputs={"success": SuccessOutput, "error": ErrorOutput},
        signal_handler_method_names=["cancel_step"],
        signal_emitters=[],
        step_object_constructor=lambda: CanplayerStep(),
    )
    def run_canplayer(
        self,
        params: CanplayerInput,
    ) -> typing.Tuple[str, typing.Union[SuccessOutput, ErrorOutput]]:
        cmd = ["stdbuf", "-oL", "canplayer", "-I", params.logfile]

        if params.verbose:
            cmd.append("-v")

        if params.infinite_loop:
            cmd.extend(["-l", "i"])
        elif params.loop_count > 1:
            cmd.extend(["-l", str(params.loop_count)])

        if params.interface:
            cmd.append(params.interface)

        try:
            print("Gathering data... Use Ctrl-C to stop.")
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            start_time = time.time()
            while True:
                if process.poll() is not None:
                    # Process exited on its own
                    break
                if self.exit.is_set() or (
                    params.timeout and (time.time() - start_time) > params.timeout
                ):
                    # Cancel signal received or timeout reached
                    print("Stopping data collection due to timeout or cancel signal.")
                    process.send_signal(signal.SIGINT)
                    time.sleep(0.5)  # Give the process a moment to flush output
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                    except Exception:
                        process.terminate()
                time.sleep(0.1)

            # Process exited on its own, collect output and continue
            stdout, stderr = process.communicate(timeout=5)
            return "success", SuccessOutput(stdout, stderr)

        except FileNotFoundError:
            return "error", ErrorOutput(1, "'canplayer' not found.")
        except subprocess.CalledProcessError as e:
            return "error", ErrorOutput(
                1, f"{e.cmd[0]} failed with return code {e.returncode}: \n{e.output}"
            )
        except (KeyboardInterrupt, SystemExit):
            print("\nReceived keyboard interrupt; Stopping data collection.\n")
            process.send_signal(signal.SIGINT)
            time.sleep(0.5)  # Give the process a moment to flush output
            try:
                stdout, stderr = process.communicate(timeout=5)
            except Exception:
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
        
        return "success", SuccessOutput(stdout, stderr)


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
                CanplayerStep.run_canplayer,
                run_cansend,
            )
        )
    )

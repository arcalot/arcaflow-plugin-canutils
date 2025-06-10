#!/usr/bin/env python3

import subprocess
import sys
import time
import typing
import threading
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

        def read_stream(stream, buffer):
            for line in iter(stream.readline, ""):
                buffer.append(line)
            stream.close()

        try:
            print("Gathering data... Use Ctrl-C to stop.")
            stdout_lines = []
            stderr_lines = []

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            stdout_thread = threading.Thread(
                target=read_stream, args=(process.stdout, stdout_lines)
            )
            stderr_thread = threading.Thread(
                target=read_stream, args=(process.stderr, stderr_lines)
            )
            stdout_thread.start()
            stderr_thread.start()

            start_time = time.time()
            while True:
                if process.poll() is not None:
                    break
                if self.exit.is_set() or (
                    params.timeout and (time.time() - start_time) > params.timeout
                ):
                    print("Stopping data collection due to timeout or cancel signal.")
                    process.terminate()
                    break
                time.sleep(0.1)

        except FileNotFoundError:
            return "error", ErrorOutput(1, "'canplayer' not found.")
        except subprocess.CalledProcessError as e:
            return "error", ErrorOutput(
                1, f"{e.cmd[0]} failed with return code {e.returncode}: \n{e.output}"
            )
        except (KeyboardInterrupt, SystemExit):
            print("\nReceived keyboard interrupt; Stopping data collection.\n")
            process.terminate()
        finally:
            # Always join threads and collect output, even after interrupt
            try:
                stdout_thread.join(timeout=2)
                stderr_thread.join(timeout=2)
            except Exception:
                pass
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

        # If we exited due to interrupt or error, return error, else success
        if self.exit.is_set() or (
            params.timeout and (time.time() - start_time) > params.timeout
        ):
            return "error", ErrorOutput(
                1, "Stopped by user or timeout.\n" + stdout + stderr
            )
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

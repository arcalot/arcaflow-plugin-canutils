#!/usr/bin/env python3

"""
Unit tests for canutils_plugin.
"""

import unittest
from unittest.mock import MagicMock, patch
import subprocess
import canutils_plugin as plugin
import arcaflow_plugin_sdk


class SchemaSerializationTest(unittest.TestCase):
    """
    Tests for the serialization and unserialization of the plugin's
    data schemas. This ensures that the data structures are compatible
    with the Arcaflow engine.
    """

    def test_canplayer_input_serialization(self):
        """
        Tests the CanplayerInput schema.
        """
        # Create an instance of the input data
        data = plugin.CanplayerInput(
            interface="vcan0",
            logfile="/tmp/test.log",
            loop_count=5,
            infinite_loop=False,
            verbose=True,
        )
        # Get the schema representation from the SDK
        data_schema = arcaflow_plugin_sdk.plugin.build_object_schema(
            plugin.CanplayerInput
        )

        # Serialize the data to a dictionary
        serialized_data = data_schema.serialize(data)

        # Define what the serialized data should look like
        expected_data = {
            "interface": "vcan0",
            "logfile": "/tmp/test.log",
            "loop_count": 5,
            "infinite_loop": False,
            "verbose": True,
        }
        self.assertEqual(serialized_data, expected_data)

        # Unserialize the data and confirm it matches the original object
        unserialized_data = data_schema.unserialize(serialized_data)
        self.assertEqual(data, unserialized_data)

    def test_cansend_input_serialization(self):
        """
        Tests the CansendInput schema.
        """
        data = plugin.CansendInput(interface="can0", frame="123#DEADBEEF")
        data_schema = arcaflow_plugin_sdk.plugin.build_object_schema(
            plugin.CansendInput
        )
        serialized_data = data_schema.serialize(data)
        expected_data = {"interface": "can0", "frame": "123#DEADBEEF"}
        self.assertEqual(serialized_data, expected_data)
        unserialized_data = data_schema.unserialize(serialized_data)
        self.assertEqual(data, unserialized_data)

    def test_success_output_serialization(self):
        """
        Tests the SuccessOutput schema.
        """
        data = plugin.SuccessOutput(stdout="some output", stderr="")
        data_schema = arcaflow_plugin_sdk.plugin.build_object_schema(
            plugin.SuccessOutput
        )
        serialized_data = data_schema.serialize(data)
        expected_data = {"stdout": "some output", "stderr": ""}
        self.assertEqual(serialized_data, expected_data)
        unserialized_data = data_schema.unserialize(serialized_data)
        self.assertEqual(data, unserialized_data)

    def test_error_output_serialization(self):
        """
        Tests the ErrorOutput schema.
        """
        data = plugin.ErrorOutput(exit_code=1, error="An error occurred")
        data_schema = arcaflow_plugin_sdk.plugin.build_object_schema(plugin.ErrorOutput)
        serialized_data = data_schema.serialize(data)
        expected_data = {"exit_code": 1, "error": "An error occurred"}
        self.assertEqual(serialized_data, expected_data)
        unserialized_data = data_schema.unserialize(serialized_data)
        self.assertEqual(data, unserialized_data)


class PluginFunctionTest(unittest.TestCase):
    """
    Tests for the plugin's step functions. These tests use mocking to
    isolate the functions from the underlying subprocess calls.
    """

    @staticmethod
    def make_mock_stream(lines):
        """
        Create a mock stream that returns lines via readline().
        """
        stream = MagicMock()
        stream.readline = MagicMock(side_effect=lines + [""])
        stream.close = MagicMock()
        return stream

    @patch("subprocess.Popen")
    def test_run_canplayer_command_construction(self, mock_popen):
        """
        Tests that canplayer is called with the correct arguments based on inputs.
        """
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.stdout = self.make_mock_stream(["line1\n", "line2\n"])
        mock_process.stderr = self.make_mock_stream(["err1\n"])
        mock_popen.return_value = mock_process

        # Test case 1: Basic execution
        params = plugin.CanplayerInput(interface="vcan0", logfile="test.log")
        plugin.CanplayerStep.run_canplayer(params=params, run_id="ci")
        expected_cmd = ['stdbuf', '-oL', "canplayer", "-I", "test.log", "-v", "vcan0"]
        mock_popen.assert_called_with(
            expected_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Test case 2: Verbose flag off
        params = plugin.CanplayerInput(interface="vcan0", logfile="t.log", verbose=False)
        plugin.CanplayerStep.run_canplayer(params=params, run_id="ci")
        expected_cmd = ['stdbuf', '-oL', "canplayer", "-I", "t.log", "vcan0"]
        mock_popen.assert_called_with(
            expected_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Test case 3: Infinite loop (should override loop_count)
        params = plugin.CanplayerInput(
            interface="vcan1", logfile="t.log", infinite_loop=True, loop_count=5
        )
        plugin.CanplayerStep.run_canplayer(params=params, run_id="ci")
        expected_cmd = ['stdbuf', '-oL', "canplayer", "-I", "t.log", "-v", "-l", "i", "vcan1"]
        mock_popen.assert_called_with(
            expected_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Test case 4: Counted loop
        params = plugin.CanplayerInput(interface="can0", logfile="t.log", loop_count=10)
        plugin.CanplayerStep.run_canplayer(params=params, run_id="ci")
        expected_cmd = ['stdbuf', '-oL', "canplayer", "-I", "t.log", "-v", "-l", "10", "can0"]
        mock_popen.assert_called_with(
            expected_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    @patch("subprocess.run")
    def test_run_cansend_success(self, mock_run):
        """
        Tests the successful execution of the cansend step.
        """
        # Configure the mock to simulate a successful run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Success output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        params = plugin.CansendInput(interface="can0", frame="123#456")
        output_id, output_data = plugin.run_cansend(params=params, run_id="ci")

        # Assert the command was called correctly
        expected_cmd = ["cansend", "can0", "123#456"]
        mock_run.assert_called_with(
            expected_cmd, capture_output=True, text=True, check=True
        )
        # Assert the output is correct
        self.assertEqual(output_id, "success")
        self.assertEqual(output_data.stdout, "Success output")

    @patch("subprocess.run")
    def test_run_cansend_process_error(self, mock_run):
        """
        Tests the cansend step when the subprocess returns an error.
        """
        # Configure the mock to simulate a process that fails
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="cansend", stderr="Device not found"
        )
        params = plugin.CansendInput(interface="can0", frame="123#456")
        output_id, output_data = plugin.run_cansend(params=params, run_id="ci")

        # Assert the output is an error with the correct details
        self.assertEqual(output_id, "error")
        self.assertEqual(output_data.exit_code, 1)
        self.assertEqual(output_data.error, "Device not found")

    @patch("subprocess.run")
    def test_run_cansend_file_not_found(self, mock_run):
        """
        Tests the cansend step when the cansend binary is not found.
        """
        # Configure the mock to simulate the command not existing
        mock_run.side_effect = FileNotFoundError("No such file or directory: 'cansend'")
        params = plugin.CansendInput(interface="can0", frame="123#456")
        output_id, output_data = plugin.run_cansend(params=params, run_id="ci")

        # Assert the output is an error with the correct details
        self.assertEqual(output_id, "error")
        self.assertEqual(output_data.exit_code, 1)
        self.assertEqual(output_data.error, "'cansend' not found.")


if __name__ == "__main__":
    unittest.main()

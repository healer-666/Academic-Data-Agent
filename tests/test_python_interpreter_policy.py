from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.tools.python_interpreter import PythonInterpreterTool  # noqa: E402
from data_analysis_agent.tool_protocol import ToolStatus  # noqa: E402


class PythonInterpreterPolicyTests(unittest.TestCase):
    def test_benchmark_policy_blocks_pip_install(self):
        previous = os.environ.get("ADA_BENCHMARK_BLOCK_PIP_INSTALL")
        os.environ["ADA_BENCHMARK_BLOCK_PIP_INSTALL"] = "1"
        try:
            response = PythonInterpreterTool().execute({"code": "import subprocess\nsubprocess.run(['pip', 'install', 'x'])"})
        finally:
            if previous is None:
                os.environ.pop("ADA_BENCHMARK_BLOCK_PIP_INSTALL", None)
            else:
                os.environ["ADA_BENCHMARK_BLOCK_PIP_INSTALL"] = previous

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(response.context.get("blocked_reason"), "pip_install_forbidden")


if __name__ == "__main__":
    unittest.main()

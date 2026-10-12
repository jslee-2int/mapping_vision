import os

# qtpy는 PyQt5·PyQt6가 같이 있으면 기본으로 PyQt5를 씁니다. ScopeFoundry 기본 .ui는 Qt6 enum 형식이라 PyQt6 uic가 필요합니다.
os.environ.setdefault("QT_API", "pyqt6")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

import sys
from pathlib import Path

# PyQt6를 sys.modules에 먼저 올려 qtpy가 PyQt5로 고정되지 않게 함
import PyQt6.QtCore  # noqa: F401

# Project root (camera_test) so `ref_code.*` imports work when run from this folder
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ScopeFoundry import BaseMicroscopeApp
from ref_code.HW_andor_spec.andor_spec_hw import AndorShamrockSpecHW


class AndorSpecTestApp(BaseMicroscopeApp):

    name = "andor_spec_test_app"

    def setup(self):
        self.add_hardware(AndorShamrockSpecHW(self))


if __name__ == "__main__":
    app = AndorSpecTestApp(sys.argv)
    app.exec_()

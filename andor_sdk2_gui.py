#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Andor SDK2 간단 GUI — FVB 스펙트럼 (ex_andor/FVB.py · SDK examples/FVB.py 흐름).

Single scan / FULL_VERTICAL_BINNING / Internal trigger · GetImages16 크기 = xpixels.

의존: NumPy, PyQt6, matplotlib, pyAndorSDK2. ANDOR_SDK = atmcd64d.dll 폴더.

실행: python andor_sdk2_gui.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _log_exception(where: str, err: BaseException) -> None:
    """PowerShell/콘솔에도 동일 오류·트레이스백 출력."""
    print(
        f"[andor_sdk2_gui][{where}] {type(err).__name__}: {err}",
        file=sys.stderr,
        flush=True,
    )
    traceback.print_exc(file=sys.stderr)

# --- 공식 Python 래퍼 경로 ---
_DEFAULT_PYANDOR_ROOT = Path(r"C:\Program Files\Andor SDK\Python\pyAndorSDK2")
# atmcd64d.dll 등 SDK2 DLL 기본 위치 (ANDOR_SDK 로 재정의 가능)
_DEFAULT_ANDOR_SDK = Path(r"C:\Program Files\Andor SDK")

# Andor SetTemperature 목표 (°C)
DETECTOR_SETPOINT_C = -70

# add_dll_directory / PATH 중복 추가 시 Windows에서 핸들·경로가 불어날 수 있음
_andor_dll_prepared = False


def _ensure_pyandor_path() -> Path | None:
    global _andor_dll_prepared
    root = Path(os.environ.get("ANDOR_PYANDOR_SDK2", _DEFAULT_PYANDOR_ROOT))
    if not root.is_dir():
        return None
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    if not _andor_dll_prepared:
        sdk_bin = Path(os.environ.get("ANDOR_SDK", str(_DEFAULT_ANDOR_SDK)))
        if sdk_bin.is_dir():
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(sdk_bin))
                except OSError:
                    pass
            sep = ";" if sys.platform == "win32" else ":"
            path = os.environ.get("PATH", "")
            parts = [p for p in path.split(sep) if p]
            if str(sdk_bin) not in parts:
                os.environ["PATH"] = str(sdk_bin) + sep + path
        _andor_dll_prepared = True
    return root


def _import_pyandor():
    _ensure_pyandor_path()
    from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

    return atmcd, atmcd_codes, atmcd_errors


import matplotlib

matplotlib.use("qtagg")
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AndorSDK2GuiWindow(QMainWindow):
    """FVB: Single scan, FULL_VERTICAL_BINNING, Internal trigger."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Andor SDK2 — FVB 스펙트럼 (pyAndorSDK2)")
        self.resize(900, 700)

        self._atmcd_mod = _import_pyandor()
        self.sdk = None
        self._codes = self._atmcd_mod[1]
        self._errs = self._atmcd_mod[2]
        self._xpixels = 0
        self._ypixels = 0
        self._fvb_pixels = 0  # GetImages16에 필요한 1D 길이 (= FVB 시 xpixels)

        self._temp_timer = QTimer(self)
        self._temp_timer.setInterval(1000)
        self._temp_timer.timeout.connect(self._update_temp_display)
        # 장비 스펙: 획득 중에는 온도 센서를 읽지 않음 (GetTemperature* 호출 금지 구간)
        self._acquisition_in_progress = False

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        info = QLabel(
            "FVB(Full Vertical Binning): 스펙트럼 = 가로 xpixels 채널.\n"
            "ANDOR_PYANDOR_SDK2 · ANDOR_SDK (atmcd64d)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        self.btn_connect = QPushButton("카메라 연결 (Initialize)")
        self.btn_connect.clicked.connect(self._on_connect)
        row.addWidget(self.btn_connect)

        self.btn_snap = QPushButton("스냅 (1프레임)")
        self.btn_snap.clicked.connect(self._on_snap)
        self.btn_snap.setEnabled(False)
        row.addWidget(self.btn_snap)

        self.btn_disconnect = QPushButton("연결 해제 (ShutDown)")
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.btn_disconnect.setEnabled(False)
        row.addWidget(self.btn_disconnect)
        layout.addLayout(row)

        form = QFormLayout()
        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(0.0001, 3600.0)
        self.spin_exposure.setDecimals(4)
        self.spin_exposure.setValue(0.05)
        self.spin_exposure.setSuffix(" s")
        form.addRow("노출 시간:", self.spin_exposure)
        layout.addLayout(form)

        self.lbl_temp = QLabel(
            f"Detector — setpoint: {DETECTOR_SETPOINT_C} °C | current: (not connected)"
        )
        self.lbl_temp.setStyleSheet("color: #1565c0;")
        self.lbl_temp.setWordWrap(True)
        layout.addWidget(self.lbl_temp)

        self.status = QLabel("대기 중")
        self.status.setStyleSheet("color: #333;")
        layout.addWidget(self.status)

        self._figure = Figure(figsize=(9, 4.5), layout="tight")
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumHeight(420)
        layout.addWidget(self._canvas)
        self._clear_spectrum_plot()

    def _ok(self, ret) -> bool:
        return int(ret) == int(self._errs.Error_Codes.DRV_SUCCESS)

    def _update_temp_display(self) -> None:
        if self.sdk is None:
            return
        if self._acquisition_in_progress:
            self.lbl_temp.setText(
                f"Detector — setpoint: {DETECTOR_SETPOINT_C} °C | "
                "current: — (not read during acquisition)"
            )
            return
        try:
            r, tc = self.sdk.GetTemperatureF()
            cur = f"{float(tc):.1f}"
            if not self._ok(r):
                cur = f"{cur} (status {int(r)})"
        except Exception as e:
            cur = f"error: {e}"
        self.lbl_temp.setText(
            f"Detector — setpoint: {DETECTOR_SETPOINT_C} °C | current: {cur} °C"
        )

    def _on_connect(self):
        try:
            atmcd, codes, errs = self._atmcd_mod
            self.sdk = atmcd("")
            ret = self.sdk.Initialize("")
            if not self._ok(ret):
                msg = f"Initialize 실패 코드: {ret}"
                print(f"[andor_sdk2_gui][연결] {msg}", file=sys.stderr, flush=True)
                QMessageBox.critical(self, "Initialize", msg)
                self.sdk = None
                return

            r, sn = self.sdk.GetCameraSerialNumber()
            if not self._ok(r):
                QMessageBox.warning(self, "Serial", f"GetCameraSerialNumber: {r}")
                sn = "?"

            r = self.sdk.SetTemperature(int(DETECTOR_SETPOINT_C))
            if not self._ok(r):
                QMessageBox.warning(
                    self,
                    "SetTemperature",
                    f"SetTemperature({DETECTOR_SETPOINT_C}) returned {r}. "
                    "Check GetTemperatureRange for this camera.",
                )

            r = self.sdk.CoolerON()
            if not self._ok(r):
                QMessageBox.warning(
                    self,
                    "Cooler",
                    f"CoolerON 실패 ({r}). 냉각 없이 진행할 수 있습니다.",
                )

            r = self.sdk.SetAcquisitionMode(codes.Acquisition_Mode.SINGLE_SCAN)
            if not self._ok(r):
                raise RuntimeError(f"SetAcquisitionMode {r}")

            r = self.sdk.SetReadMode(codes.Read_Mode.FULL_VERTICAL_BINNING)
            if not self._ok(r):
                raise RuntimeError(f"SetReadMode FVB {r}")

            r = self.sdk.SetTriggerMode(codes.Trigger_Mode.INTERNAL)
            if not self._ok(r):
                raise RuntimeError(f"SetTriggerMode {r}")

            r, self._xpixels, self._ypixels = self.sdk.GetDetector()
            if not self._ok(r):
                raise RuntimeError(f"GetDetector {r}")

            # FVB: 버퍼 길이 = xpixels (examples/FVB.py)
            self._fvb_pixels = int(self._xpixels)

            self.status.setText(
                f"연결됨 — serial={sn}, FVB 길이={self._fvb_pixels} (detector {self._xpixels}×{self._ypixels})"
            )
            self._update_temp_display()
            self._temp_timer.start()
            self.btn_snap.setEnabled(True)
            self.btn_disconnect.setEnabled(True)
            self.btn_connect.setEnabled(False)
        except Exception as e:
            self.sdk = None
            self._temp_timer.stop()
            self.lbl_temp.setText(
                f"Detector — setpoint: {DETECTOR_SETPOINT_C} °C | current: (not connected)"
            )
            _log_exception("연결", e)
            QMessageBox.critical(self, "오류", str(e))
            self.status.setText(f"오류: {e}")

    def _on_snap(self):
        if self.sdk is None:
            return
        exp = float(self.spin_exposure.value())
        try:
            try:
                self.sdk.AbortAcquisition()
            except Exception:
                pass

            self.sdk.SetExposureTime(exp)
            # (ret, exposure, accumulate, kinetic) — 4개 반환
            r, _, _, _ = self.sdk.GetAcquisitionTimings()
            if not self._ok(r):
                pass

            self._acquisition_in_progress = True
            self._update_temp_display()

            r = self.sdk.PrepareAcquisition()
            if not self._ok(r):
                raise RuntimeError(f"PrepareAcquisition {r}")

            r = self.sdk.StartAcquisition()
            if not self._ok(r):
                raise RuntimeError(f"StartAcquisition {r}")

            r = self.sdk.WaitForAcquisition()
            if not self._ok(r):
                raise RuntimeError(f"WaitForAcquisition {r}")

            image_size = self._fvb_pixels
            r, arr, vf, vl = self.sdk.GetImages16(1, 1, image_size)
            if not self._ok(r):
                raise RuntimeError(f"GetImages16 {r}")

            data = np.asarray(arr, dtype=np.int16).reshape(-1)[:image_size]
            self._show_spectrum_u16(data)
            self.status.setText(
                f"FVB 스펙트럼 — min={int(data.min())} max={int(data.max())}, 채널={len(data)}"
            )
        except Exception as e:
            _log_exception("스냅", e)
            QMessageBox.critical(self, "스냅 실패", str(e))
            self.status.setText(str(e))
        finally:
            self._acquisition_in_progress = False
            try:
                self.sdk.AbortAcquisition()
            except Exception:
                pass
            if self.sdk is not None:
                self._update_temp_display()

    def _clear_spectrum_plot(self) -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_facecolor("#1a1a1a")
        self._figure.patch.set_facecolor("#222")
        ax.tick_params(colors="#ccc")
        ax.xaxis.label.set_color("#ccc")
        ax.yaxis.label.set_color("#ccc")
        ax.set_title("FVB 1D spectrum", color="#eee", fontsize=11)
        ax.set_xlabel("Pixel (channel index)")
        ax.set_ylabel("Intensity (counts)")
        ax.text(
            0.5,
            0.5,
            "Connect and snap",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="#888",
            fontsize=12,
        )
        self._canvas.draw_idle()

    def _show_spectrum_u16(self, spec: np.ndarray) -> None:
        """FVB 1D 스펙트럼: x = 픽셀(채널) 인덱스 0 … N-1, y = 강도."""
        s = np.asarray(spec, dtype=np.float64).ravel()
        n = len(s)
        x = np.arange(n, dtype=np.float64)

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_facecolor("#1a1a1a")
        self._figure.patch.set_facecolor("#222")
        ax.tick_params(colors="#ccc")
        ax.xaxis.label.set_color("#ccc")
        ax.yaxis.label.set_color("#ccc")
        ax.plot(x, s, color="#4fc3f7", lw=0.9, drawstyle="default")
        ax.set_xlabel("Pixel (channel index)")
        ax.set_ylabel("Intensity (counts)")
        ax.set_title("FVB 1D spectrum", color="#eee", fontsize=11)
        ax.set_xlim(0, max(n - 1, 1))
        ax.grid(True, alpha=0.25, color="#555")
        self._figure.tight_layout()
        self._canvas.draw_idle()

    def _on_disconnect(self):
        if self.sdk is not None:
            try:
                self.sdk.AbortAcquisition()
            except Exception:
                pass
            try:
                r = self.sdk.ShutDown()
                if not self._ok(r):
                    msg = f"ShutDown 코드: {r}"
                    print(f"[andor_sdk2_gui][연결 해제] {msg}", file=sys.stderr, flush=True)
                    QMessageBox.warning(self, "ShutDown", msg)
            except Exception as e:
                _log_exception("연결 해제 ShutDown", e)
                QMessageBox.warning(self, "ShutDown", str(e))
            self.sdk = None
        self._temp_timer.stop()
        self.lbl_temp.setText(
            f"Detector — setpoint: {DETECTOR_SETPOINT_C} °C | current: (not connected)"
        )
        self._xpixels = self._ypixels = self._fvb_pixels = 0
        self.btn_snap.setEnabled(False)
        self.btn_disconnect.setEnabled(False)
        self.btn_connect.setEnabled(True)
        self.status.setText("ShutDown 완료")
        self._clear_spectrum_plot()

    def closeEvent(self, event):
        self._on_disconnect()
        event.accept()


def main():
    if _ensure_pyandor_path() is None:
        print(
            "pyAndorSDK2 폴더를 찾을 수 없습니다. ANDOR_PYANDOR_SDK2 로 경로를 지정하세요.",
            file=sys.stderr,
        )
        return 1
    app = QApplication(sys.argv)
    w = AndorSDK2GuiWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

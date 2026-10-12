# Andor SDK2 — ui_sdk2 폼용 로직 (andor_sdk2_gui.py 연결·냉각·FVB 획득과 동일)

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QVBoxLayout,
    QWidget,
)

from ui_sdk2 import Ui_Form

from andor_sdk2_gui import (
    DETECTOR_SETPOINT_C,
    _ensure_pyandor_path,
    _import_pyandor,
    _log_exception,
)
from sub_py.matplotlibwidget import MatplotlibWidget
from sub_py.read_sif import SIF

# Andor SDK2: GetImages16 등이 "새 데이터 없음"을 반환 (Stop 시 Abort 직후 흔함)
# pylablib atmcd32d_defs.DRV_NO_NEW_DATA 와 동일 명칭
_ANDOR_DRV_NO_NEW_DATA = 20024


class AcquisitionInterruptedError(Exception):
    """Abort/Stop 직후 GetImages16이 DRV_NO_NEW_DATA(20024)인 경우 — 실시간 루프 정상 종료로 처리."""


class RealtimeFvbThread(QThread):
    """FVB 연속 획득을 메인 스레드가 아닌 워커에서 수행해 전체 UI(메인 창 카메라 등) 응답 유지."""

    frame_ready = pyqtSignal(object)
    acquisition_busy = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, form: "AndorSdk2FormWidget"):
        super().__init__(form)
        self._form = form
        self._run = False

    def request_stop(self) -> None:
        self._run = False

    def run(self) -> None:
        self._run = True
        f = self._form
        while self._run:
            try:
                self.acquisition_busy.emit(True)
                data = f._capture_fvb_core()
                self.acquisition_busy.emit(False)
                if not self._run:
                    break
                self.frame_ready.emit(data)
            except AcquisitionInterruptedError:
                # Stop 시 Abort → GetImages16 20024(DRV_NO_NEW_DATA) 는 정상적인 종료 경로
                self.acquisition_busy.emit(False)
                break
            except Exception as e:
                self.acquisition_busy.emit(False)
                self.error_occurred.emit(str(e))
                _log_exception("Real time (worker)", e)
                break
        self.acquisition_busy.emit(False)


class AndorSdk2FormWidget(QWidget):
    """SDK2 연결, FVB 측정(Background / Real time / Single shot), matplotlib 플롯."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.setWindowTitle("Andor SDK2")

        self.sdk = None
        self._atmcd_mod = None
        self._xpixels = 0
        self._ypixels = 0
        self._fvb_pixels = 0
        self._acquisition_in_progress = False
        self._bg_data: np.ndarray | None = None
        self._realtime_running = False
        self._realtime_thread: RealtimeFvbThread | None = None
        self._exposure_sec_cached = float(self.ui.dsb_expoT.value())
        self._xcal_wavelength_nm: np.ndarray | None = None
        self._config_loading = False
        self._config_dirty = False

        self._temp_timer = QTimer(self)
        self._temp_timer.setInterval(5000)
        self._temp_timer.timeout.connect(self._update_temp_display)

        self._setup_plot_panels()
        self._setup_exposure_spin()
        self._setup_connect_toggle()
        self._setup_measure_buttons()
        self._setup_xcal()
        self._setup_config()
        self._load_config_file()
        self._connect_config_dirty_signals()

        if _ensure_pyandor_path() is None:
            self.ui.btn_sdk2_connect.setToolTip(
                "pyAndorSDK2 폴더를 찾을 수 없습니다. 환경 변수 ANDOR_PYANDOR_SDK2 로 경로를 지정하세요."
            )

    def _setup_plot_panels(self) -> None:
        lay_d = QVBoxLayout(self.ui.widget)
        lay_d.setContentsMargins(0, 0, 0, 0)
        self._mpl_data = MatplotlibWidget(
            parent=self.ui.widget,
            title="FVB (Data)",
            xlabel="Pixel (channel)",
            ylabel="Counts",
            width=5,
            height=3.5,
            hold=True,
        )
        lay_d.addWidget(self._mpl_data)

        lay_b = QVBoxLayout(self.ui.widget_2)
        lay_b.setContentsMargins(0, 0, 0, 0)
        self._mpl_bg = MatplotlibWidget(
            parent=self.ui.widget_2,
            title="Background FVB",
            xlabel="Pixel (channel)",
            ylabel="Counts",
            width=5,
            height=3.5,
            hold=True,
        )
        lay_b.addWidget(self._mpl_bg)

    def _setup_exposure_spin(self) -> None:
        self.ui.dsb_expoT.setRange(0.0001, 3600.0)
        self.ui.dsb_expoT.setDecimals(4)
        self.ui.dsb_expoT.setValue(0.05)
        self._exposure_sec_cached = float(self.ui.dsb_expoT.value())
        self.ui.dsb_expoT.valueChanged.connect(self._on_exposure_cache_changed)

    def _on_exposure_cache_changed(self, value: float) -> None:
        self._exposure_sec_cached = float(value)

    def apply_exposure_from_ui(self) -> float:
        """
        dsb_expoT(초) → _exposure_sec_cached. Single shot / Mapping / Background 모두
        _capture_fvb() 직전에 동일하게 적용된다.
        """
        sec = float(self.ui.dsb_expoT.value())
        self._exposure_sec_cached = sec
        return sec

    def _setup_connect_toggle(self) -> None:
        self.ui.btn_sdk2_connect.setCheckable(True)
        self.ui.btn_sdk2_connect.setChecked(False)
        self.ui.btn_sdk2_connect.setText("SDK2 Connect")
        self.ui.btn_sdk2_connect.setStyleSheet(
            "QPushButton:checked {\n"
            "    background-color: #4CAF50;\n"
            "    color: white;\n"
            "}"
        )
        self.ui.btn_sdk2_connect.clicked.connect(self._on_sdk2_toggle)

    def _setup_measure_buttons(self) -> None:
        for b in (self.ui.btn_bakg, self.ui.btn_realtime, self.ui.btn_singleshot):
            b.setEnabled(False)
        self.ui.btn_bakg.clicked.connect(self._on_background)
        self.ui.btn_singleshot.clicked.connect(self._on_singleshot)

        self.ui.btn_realtime.setCheckable(True)
        self.ui.btn_realtime.setStyleSheet(
            "QPushButton:checked {\n"
            "    background-color: #4CAF50;\n"
            "    color: white;\n"
            "}"
        )
        self.ui.btn_realtime.clicked.connect(self._on_realtime_clicked)

    def _setup_xcal(self) -> None:
        self.ui.btn_xcalfile.clicked.connect(self._on_xcal_open_file)

    @staticmethod
    def _config_filepath() -> Path:
        return Path(__file__).resolve().parent / "sdk2_form_config.json"

    def _setup_config(self) -> None:
        self.ui.btn_conf.setEnabled(False)
        self.ui.btn_conf.clicked.connect(self._on_save_configuration)
        self.ui.btn_dirPath.clicked.connect(self._on_dirpath_browse)
        self.ui.btn_save_Spectrum.clicked.connect(self._on_save_spectrum)

    def _on_dirpath_browse(self) -> None:
        cur = self.ui.lineEdit_dirpath.text().strip()
        start = cur if cur and Path(cur).is_dir() else ""
        path = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", start)
        if path:
            self.ui.lineEdit_dirpath.setText(path)

    def _connect_config_dirty_signals(self) -> None:
        self.ui.dsb_expoT.valueChanged.connect(self._mark_config_dirty)
        self.ui.chk_xcal.stateChanged.connect(self._mark_config_dirty)
        self.ui.lineEdit_dirpath.textChanged.connect(self._mark_config_dirty)
        self.ui.lineEdit_groupname.textChanged.connect(self._mark_config_dirty)
        self.ui.lineEdit_fileName.textChanged.connect(self._mark_config_dirty)

    def _mark_config_dirty(self, *args) -> None:
        if self._config_loading:
            return
        self._config_dirty = True
        self.ui.btn_conf.setEnabled(True)

    def _collect_config_dict(self) -> dict:
        xp = self.ui.label_xcal_path.text().strip()
        if xp == "-" or not xp:
            xp = ""
        return {
            "expose_time_sec": float(self.ui.dsb_expoT.value()),
            "xcal_file_path": xp,
            "xcal_apply": self.ui.chk_xcal.isChecked(),
            "save_dir_path": self.ui.lineEdit_dirpath.text().strip(),
            "group_name": self.ui.lineEdit_groupname.text().strip(),
            "file_name": self.ui.lineEdit_fileName.text().strip(),
        }

    def _apply_config_dict(self, d: dict) -> None:
        if not isinstance(d, dict):
            return
        self._config_loading = True
        try:
            et = float(d.get("expose_time_sec", 0.05))
            self.ui.dsb_expoT.setValue(et)
            self._exposure_sec_cached = float(self.ui.dsb_expoT.value())
            self.ui.chk_xcal.setChecked(bool(d.get("xcal_apply", False)))
            path = str(d.get("xcal_file_path", "") or "").strip()
            self._load_xcal_from_path(path, log_on_error=False)
            self.ui.lineEdit_dirpath.setText(str(d.get("save_dir_path", "") or ""))
            self.ui.lineEdit_groupname.setText(str(d.get("group_name", "") or ""))
            self.ui.lineEdit_fileName.setText(str(d.get("file_name", "") or ""))
        finally:
            self._config_loading = False

    def _load_config_file(self) -> None:
        p = self._config_filepath()
        if not p.is_file():
            self._config_dirty = False
            self.ui.btn_conf.setEnabled(False)
            return
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            self._apply_config_dict(d)
        except Exception as e:
            _log_exception("sdk2 config load", e)
            self._append_log(f"설정 파일 불러오기 실패: {e}")
        self._config_dirty = False
        self.ui.btn_conf.setEnabled(False)

    def _append_log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.ui.plainTextEdit_logs.appendPlainText(f"[{ts}] {message}")

    def resolve_mapping_csv_path(self, stem: str) -> Path | None:
        """
        매핑 등에서 저장할 CSV 전체 경로. Save Spectrum과 동일 규칙:
        DIR Path / [Group Name /] stem.csv
        Group Name이 비어 있으면 DIR Path 바로 아래에 stem.csv.
        """
        base = self.ui.lineEdit_dirpath.text().strip()
        if not base:
            return None
        stem = (stem or "").strip()
        if not stem:
            return None
        if stem.lower().endswith(".csv"):
            fn = stem
        else:
            fn = f"{stem}.csv"
        group = self.ui.lineEdit_groupname.text().strip()
        root = Path(base)
        if group:
            return (root / group / fn).resolve()
        return (root / fn).resolve()

    def _active_mpl_for_save(self) -> MatplotlibWidget:
        """현재 선택된 탭의 스펙트럼 플롯 (Data=0 → _mpl_data, BG=1 → _mpl_bg)."""
        if self.ui.tabWidget.currentIndex() == 1:
            return self._mpl_bg
        return self._mpl_data

    @staticmethod
    def _extract_plot_xy(mpl: MatplotlibWidget) -> tuple[np.ndarray, np.ndarray, str, str]:
        ax = mpl.axes
        lines = ax.get_lines()
        if not lines:
            raise ValueError("플롯에 곡선이 없습니다. 먼저 측정하세요.")
        ln = lines[0]
        x = np.asarray(ln.get_xdata(), dtype=np.float64).ravel()
        y = np.asarray(ln.get_ydata(), dtype=np.float64).ravel()
        if x.size == 0 or y.size == 0:
            raise ValueError("플롯 데이터가 비어 있습니다.")
        n = min(x.size, y.size)
        x, y = x[:n], y[:n]
        xlabel = (ax.get_xlabel() or "x").strip() or "x"
        ylabel = (ax.get_ylabel() or "y").strip() or "y"
        return x, y, xlabel, ylabel

    def _on_save_spectrum(self) -> bool:
        """Save Spectrum 버튼과 동일. 플롯 축 라벨·X-cal 반영 CSV 저장. 성공 시 True."""
        base = self.ui.lineEdit_dirpath.text().strip()
        group = self.ui.lineEdit_groupname.text().strip()
        fn = self.ui.lineEdit_fileName.text().strip()
        if not base:
            self._append_log("Save Spectrum: DIR Path를 입력하세요.")
            return False
        if not group:
            self._append_log("Save Spectrum: Group Name을 입력하세요.")
            return False
        if not fn:
            self._append_log("Save Spectrum: File Name을 입력하세요.")
            return False
        if not fn.lower().endswith(".csv"):
            fn = fn + ".csv"
        try:
            mpl = self._active_mpl_for_save()
            x, y, xlabel, ylabel = self._extract_plot_xy(mpl)
        except ValueError as e:
            self._append_log(f"Save Spectrum: {e}")
            return False
        except Exception as e:
            _log_exception("Save Spectrum extract", e)
            self._append_log(f"Save Spectrum: 플롯 읽기 실패: {e}")
            return False

        try:
            root = Path(base)
            out = (root / group / fn).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", newline="", encoding="utf-8") as fp:
                w = csv.writer(fp)
                w.writerow([xlabel, ylabel])
                for xi, yi in zip(x, y):
                    w.writerow([float(xi), float(yi)])
            self._append_log(f"Save Spectrum: 저장 완료 {out}")
            return True
        except Exception as e:
            _log_exception("Save Spectrum write", e)
            self._append_log(f"Save Spectrum: 파일 저장 실패: {e}")
            return False

    def _on_save_configuration(self) -> None:
        if not self._config_dirty:
            self._append_log("설정: 저장할 변경 사항이 없습니다.")
            return
        p = self._config_filepath()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self._collect_config_dict(), f, ensure_ascii=False, indent=2)
            self._config_dirty = False
            self.ui.btn_conf.setEnabled(False)
            self._append_log(f"설정 저장 완료: {p}")
        except Exception as e:
            _log_exception("sdk2 config save", e)
            self._append_log(f"설정 저장 실패: {e}")

    def _load_xcal_from_path(self, path: str, log_on_error: bool = True) -> bool:
        path = (path or "").strip()
        if not path or path == "-":
            self.ui.label_xcal_path.setText("-")
            self.ui.label_xcal_path.setToolTip("")
            self._xcal_wavelength_nm = None
            return False
        self.ui.label_xcal_path.setText(path)
        self.ui.label_xcal_path.setToolTip(path)
        try:
            sif_read = SIF(path)
            wavelength, _intensity = sif_read.read()
            self._xcal_wavelength_nm = np.asarray(wavelength, dtype=np.float64).ravel()
            return True
        except Exception as e:
            self._xcal_wavelength_nm = None
            _log_exception("X-cal SIF", e)
            if log_on_error:
                self._append_log(f"SIF 읽기 실패: {e}")
            return False

    def _on_xcal_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "X-calibration SIF",
            "",
            "SIF files (*.sif *.SIF);;All files (*.*)",
        )
        if not path:
            return
        self._load_xcal_from_path(path, log_on_error=True)
        self._mark_config_dirty()

    def _x_axis_for_plot(self, n: int) -> tuple[np.ndarray, str, str]:
        """chk_xcal + 캘리브레이션 길이가 맞으면 파장(nm), 아니면 픽셀 인덱스."""
        if (
            self.ui.chk_xcal.isChecked()
            and self._xcal_wavelength_nm is not None
        ):
            w = self._xcal_wavelength_nm
            if w.size == n:
                return w.copy(), "Wavelength (nm)", ""
            return (
                np.arange(n, dtype=np.float64),
                "Pixel (channel)",
                f" (x-cal mismatch: {w.size}≠{n})",
            )
        return np.arange(n, dtype=np.float64), "Pixel (channel)", ""

    def _set_measure_buttons_enabled(self, connected: bool) -> None:
        if not connected:
            self.ui.btn_bakg.setEnabled(False)
            self.ui.btn_realtime.setEnabled(False)
            self.ui.btn_singleshot.setEnabled(False)
            return
        if self._realtime_running:
            self.ui.btn_bakg.setEnabled(False)
            self.ui.btn_singleshot.setEnabled(False)
            self.ui.btn_realtime.setEnabled(True)
        else:
            self.ui.btn_bakg.setEnabled(True)
            self.ui.btn_realtime.setEnabled(True)
            self.ui.btn_singleshot.setEnabled(True)

    def _ok(self, ret) -> bool:
        return int(ret) == int(self._atmcd_mod[2].Error_Codes.DRV_SUCCESS)

    def _update_temp_display(self) -> None:
        if self.sdk is None:
            self.ui.label_6.setText("--")
            return
        if self._acquisition_in_progress:
            self.ui.label_6.setText("—")
            return
        try:
            r, tc = self.sdk.GetTemperatureF()
            cur = f"{float(tc):.1f}"
            if not self._ok(r):
                cur = f"{cur} ({int(r)})"
        except Exception as e:
            cur = f"err:{e}"
        self.ui.label_6.setText(f"{cur} °C")

    def _on_acquisition_busy_from_thread(self, busy: bool) -> None:
        self._acquisition_in_progress = busy
        self._update_temp_display()

    def _plot_fvb(self, mpl: MatplotlibWidget, data: np.ndarray, title: str) -> None:
        ax = mpl.axes
        ax.clear()
        y = np.asarray(data, dtype=np.float64).ravel()
        n = y.size
        x, xlabel, x_note = self._x_axis_for_plot(n)
        ax.plot(x, y, color="#4fc3f7", lw=0.9)
        ax.set_title(title + x_note)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Counts")
        mpl.figure.tight_layout()
        mpl.draw_idle()

    def _plot_fvb_with_optional_bg(
        self, mpl: MatplotlibWidget, raw: np.ndarray, title: str
    ) -> None:
        """Background가 있으면 raw − bg 로 Data 탭 플롯, 없으면 raw 그대로."""
        if self._bg_data is None:
            self._plot_fvb(mpl, raw, title)
            return
        bg = np.asarray(self._bg_data, dtype=np.float64).ravel()
        r = np.asarray(raw, dtype=np.float64).ravel()
        if bg.size != r.size:
            self._plot_fvb(
                mpl,
                raw,
                f"{title} (bg not applied: length {r.size} vs {bg.size})",
            )
            return
        corrected = r - bg
        self._plot_fvb(mpl, corrected, f"{title} (bg subtracted)")

    def _capture_fvb_core(self) -> np.ndarray:
        """UI 없이 SDK만. 메인/워커 스레드에서 호출 가능(동시 호출 금지)."""
        if self.sdk is None or self._fvb_pixels <= 0:
            raise RuntimeError("Camera not ready (connect first).")
        try:
            try:
                self.sdk.AbortAcquisition()
            except Exception:
                pass

            exp = self._exposure_sec_cached
            self.sdk.SetExposureTime(exp)
            r, _, _, _ = self.sdk.GetAcquisitionTimings()
            if not self._ok(r):
                pass

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
                if int(r) == _ANDOR_DRV_NO_NEW_DATA:
                    raise AcquisitionInterruptedError(
                        "GetImages16 DRV_NO_NEW_DATA (20024): no frame after abort/stop"
                    )
                raise RuntimeError(f"GetImages16 {r}")

            data = np.asarray(arr, dtype=np.int16).reshape(-1)[:image_size]
            return data
        finally:
            try:
                self.sdk.AbortAcquisition()
            except Exception:
                pass

    def _capture_fvb(self) -> np.ndarray:
        """메인 스레드 전용: 노출 UI 반영, 측정 중 온도 표시, processEvents."""
        self.apply_exposure_from_ui()
        try:
            self._acquisition_in_progress = True
            self._update_temp_display()
            QApplication.processEvents()
            return self._capture_fvb_core()
        finally:
            self._acquisition_in_progress = False
            if self.sdk is not None:
                self._update_temp_display()

    def acquire_fvb_xy_for_mapping(self) -> tuple[np.ndarray, np.ndarray] | None:
        """
        메인 창 mapping용: FVB 1회 측정 후 (x, counts) 반환.
        BG 차감·X-cal·노출(dsb_expoT)은 Single shot과 동일 경로(_capture_fvb).
        """
        if self.sdk is None:
            return None
        if self._realtime_running:
            self._stop_realtime()
        try:
            data = self._capture_fvb()
            self._plot_fvb_with_optional_bg(self._mpl_data, data, "Mapping FVB")
            self.ui.tabWidget.setCurrentWidget(self.ui.tab)
            raw = np.asarray(data, dtype=np.float64).ravel()
            n = raw.size
            if self._bg_data is not None:
                bg = np.asarray(self._bg_data, dtype=np.float64).ravel()
                if bg.size == n:
                    y = raw - bg
                else:
                    y = raw
            else:
                y = raw
            x, _xlabel, _x_note = self._x_axis_for_plot(n)
            return x, y
        except Exception as e:
            _log_exception("acquire_fvb_xy_for_mapping", e)
            self._append_log(f"Mapping FVB 오류: {e}")
            return None

    def _on_background(self) -> None:
        if self.sdk is None:
            self._append_log("SDK2: 카메라를 먼저 연결하세요.")
            return
        if self._realtime_running:
            self._stop_realtime()
        try:
            data = self._capture_fvb()
            self._bg_data = data.copy()
            self._plot_fvb(self._mpl_bg, data, "Background FVB")
            self.ui.tabWidget.setCurrentWidget(self.ui.tab_2)
        except Exception as e:
            _log_exception("Background", e)
            self._append_log(f"Background 오류: {e}")

    def _on_singleshot(self) -> None:
        if self.sdk is None:
            self._append_log("SDK2: 카메라를 먼저 연결하세요.")
            return
        if self._realtime_running:
            self._stop_realtime()
        try:
            data = self._capture_fvb()
            self._plot_fvb_with_optional_bg(self._mpl_data, data, "Single shot FVB")
            self.ui.tabWidget.setCurrentWidget(self.ui.tab)
        except Exception as e:
            _log_exception("Single shot", e)
            self._append_log(f"Acquisition 오류: {e}")

    def _on_realtime_clicked(self) -> None:
        if self.sdk is None:
            self._append_log("SDK2: 카메라를 먼저 연결하세요.")
            self.ui.btn_realtime.blockSignals(True)
            self.ui.btn_realtime.setChecked(False)
            self.ui.btn_realtime.blockSignals(False)
            return
        if self.ui.btn_realtime.isChecked():
            self._exposure_sec_cached = float(self.ui.dsb_expoT.value())
            self._realtime_running = True
            self.ui.btn_realtime.setText("Real Time (Stop)")
            self._set_measure_buttons_enabled(True)
            self._start_realtime_thread()
        else:
            self._stop_realtime()

    def _start_realtime_thread(self) -> None:
        self._stop_realtime_thread_only()
        th = RealtimeFvbThread(self)
        qc = Qt.ConnectionType.QueuedConnection
        th.frame_ready.connect(self._on_realtime_frame, qc)
        th.acquisition_busy.connect(self._on_acquisition_busy_from_thread, qc)
        th.error_occurred.connect(self._on_realtime_thread_error, qc)
        th.finished.connect(self._on_realtime_thread_finished)
        self._realtime_thread = th
        th.start()

    def _on_realtime_frame(self, data: object) -> None:
        arr = np.asarray(data)
        self._plot_fvb_with_optional_bg(self._mpl_data, arr, "Real time FVB")
        self.ui.tabWidget.setCurrentWidget(self.ui.tab)

    def _on_realtime_thread_error(self, msg: str) -> None:
        self._append_log(f"Real time 오류: {msg}")
        self._stop_realtime()

    def _on_realtime_thread_finished(self) -> None:
        self._realtime_thread = None

    def _stop_realtime_thread_only(self) -> None:
        if self._realtime_thread is None:
            return
        self._realtime_thread.request_stop()
        if self.sdk is not None:
            try:
                self.sdk.AbortAcquisition()
            except Exception:
                pass
        if not self._realtime_thread.wait(20000):
            print(
                "[sdk2_form_widget] Real time thread did not stop in time",
                file=sys.stderr,
                flush=True,
            )
        self._realtime_thread = None

    def _stop_realtime(self, update_measure_buttons: bool = True) -> None:
        self._realtime_running = False
        self.ui.btn_realtime.blockSignals(True)
        self.ui.btn_realtime.setChecked(False)
        self.ui.btn_realtime.setText("Real Time")
        self.ui.btn_realtime.blockSignals(False)
        self._stop_realtime_thread_only()
        self._acquisition_in_progress = False
        if self.sdk is not None:
            self._update_temp_display()
        if update_measure_buttons and self.sdk is not None:
            self._set_measure_buttons_enabled(True)

    def _clear_connection_status_labels(self) -> None:
        self.ui.label_serial.setText("-")
        self.ui.label_fvb.setText("-")
        self.ui.label_setTemp.setText("-")

    def _set_connection_status_labels(
        self,
        serial: str,
        fvb_pixels: int,
        xpixels: int,
        ypixels: int,
        set_temp_c: int,
    ) -> None:
        self.ui.label_serial.setText(str(serial))
        self.ui.label_fvb.setText(f"{fvb_pixels} ({xpixels}×{ypixels})")
        self.ui.label_setTemp.setText(f"{set_temp_c} °C")

    def _apply_ui_disconnected(self) -> None:
        self._stop_realtime(update_measure_buttons=False)
        self.ui.btn_sdk2_connect.blockSignals(True)
        self.ui.btn_sdk2_connect.setChecked(False)
        self.ui.btn_sdk2_connect.setText("SDK2 Connect")
        self.ui.btn_sdk2_connect.blockSignals(False)
        self._clear_connection_status_labels()
        self._set_measure_buttons_enabled(False)

    def _on_sdk2_toggle(self) -> None:
        if self.ui.btn_sdk2_connect.isChecked():
            self._try_connect_sdk()
        else:
            self._sdk2_shutdown()

    def _try_connect_sdk(self) -> None:
        if _ensure_pyandor_path() is None:
            self._append_log(
                "pyAndorSDK2: 폴더를 찾을 수 없습니다. "
                "환경 변수 ANDOR_PYANDOR_SDK2 로 경로를 지정하세요."
            )
            self._apply_ui_disconnected()
            return

        try:
            if self._atmcd_mod is None:
                self._atmcd_mod = _import_pyandor()
            atmcd, codes, errs = self._atmcd_mod

            self.sdk = atmcd("")
            ret = self.sdk.Initialize("")
            if not self._ok(ret):
                msg = f"Initialize 실패 코드: {ret}"
                print(f"[sdk2_form_widget][연결] {msg}", file=sys.stderr, flush=True)
                self._append_log(f"Initialize 실패: {msg}")
                self.sdk = None
                self._apply_ui_disconnected()
                return

            r, sn = self.sdk.GetCameraSerialNumber()
            if not self._ok(r):
                self._append_log(f"Serial 경고: GetCameraSerialNumber 코드 {r}")
                sn = "?"

            r = self.sdk.SetTemperature(int(DETECTOR_SETPOINT_C))
            if not self._ok(r):
                self._append_log(
                    f"SetTemperature 경고: SetTemperature({DETECTOR_SETPOINT_C}) "
                    f"반환 {r}. GetTemperatureRange 확인."
                )

            r = self.sdk.CoolerON()
            if not self._ok(r):
                self._append_log(f"Cooler 경고: CoolerON 실패 ({r}). 냉각 없이 진행할 수 있습니다.")

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

            self._fvb_pixels = int(self._xpixels)

            self._update_temp_display()
            self._temp_timer.start()
            self.ui.btn_sdk2_connect.setText("SDK2 Connected")
            self._set_measure_buttons_enabled(True)
            self._set_connection_status_labels(
                str(sn),
                self._fvb_pixels,
                int(self._xpixels),
                int(self._ypixels),
                int(DETECTOR_SETPOINT_C),
            )
            self.setWindowTitle("Andor SDK2")
        except Exception as e:
            self.sdk = None
            self._temp_timer.stop()
            self.ui.label_6.setText("--")
            _log_exception("SDK2 연결", e)
            self._append_log(f"SDK2 연결 오류: {e}")
            self.setWindowTitle("Andor SDK2")
            self._apply_ui_disconnected()

    def _sdk2_shutdown(self) -> None:
        self._stop_realtime(update_measure_buttons=False)
        if self.sdk is not None:
            try:
                self.sdk.AbortAcquisition()
            except Exception:
                pass
            try:
                r = self.sdk.ShutDown()
                if self._atmcd_mod is not None and int(r) != int(
                    self._atmcd_mod[2].Error_Codes.DRV_SUCCESS
                ):
                    msg = f"ShutDown 코드: {r}"
                    print(f"[sdk2_form_widget][연결 해제] {msg}", file=sys.stderr, flush=True)
                    self._append_log(f"ShutDown 경고: {msg}")
            except Exception as e:
                _log_exception("ShutDown", e)
                self._append_log(f"ShutDown 예외: {e}")
            self.sdk = None
        self._temp_timer.stop()
        self._xpixels = self._ypixels = self._fvb_pixels = 0
        self._bg_data = None
        self.ui.label_6.setText("--")
        self._apply_ui_disconnected()
        self.setWindowTitle("Andor SDK2")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._sdk2_shutdown()
        event.accept()

import sys
import matplotlib
from PyQt6 import QtCore, QtWidgets, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


class ToolbarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ToolbarWidget, self).__init__(parent)

    def read(self, canvas):
        # 기본 스타일 설정
        matplotlib.style.use('dark_background')
        
        toolbar = NavigationToolbar(canvas, self)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2D2D2D;
                border: none;
                spacing: 5px;
                padding: 5px;
            }
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 5px;
                min-width: 30px;
                min-height: 30px;
            }
            QToolButton:hover {
                background-color: #3D3D3D;
                border-radius: 4px;
            }
            QToolButton:pressed {
                background-color: #4D4D4D;
            }
        """)
        
        # 아이콘 크기 조정
        toolbar.setIconSize(QtCore.QSize(24, 24))
        
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Pierre Raybaut
# Licensed under the terms of the MIT License

"""
MatplotlibWidget
================
Example of matplotlib widget for PyQt4
Copyright © 2009 Pierre Raybaut
This software is licensed under the terms of the MIT License
Derived from 'embedding_in_pyqt4.py':
Copyright © 2005 Florent Rougon, 2006 Darren Dale
"""

__version__ = "1.0.0"

from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtCore import QSize
from qbstyles import mpl_style

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from matplotlib import rcParams

rcParams['font.size'] = 7


class MatplotlibWidget(Canvas):
    """
    MatplotlibWidget inherits PyQt4.QtGui.QWidget
    and matplotlib.backend_bases.FigureCanvasBase

    Options: option_name (default_value)
    -------
    parent (None): parent widget
    title (''): figure title
    xlabel (''): X-axis label
    ylabel (''): Y-axis label
    xlim (None): X-axis limits ([min, max])
    ylim (None): Y-axis limits ([min, max])
    xscale ('linear'): X-axis scale
    yscale ('linear'): Y-axis scale
    width (4): width in inches
    height (3): height in inches
    dpi (100): resolution in dpi
    hold (False): if False, figure will be cleared each time plot is called

    Widget attributes:
    -----------------
    figure: instance of matplotlib.figure.Figure
    axes: figure axes

    Example:
    -------
    self.widget = MatplotlibWidget(self, yscale='log', hold=True)
    from numpy import linspace
    x = linspace(-10, 10)
    self.widget.axes.plot(x, x**2)
    self.wdiget.axes.plot(x, x**3)
    """

    def __init__(self, parent=None, title='', xlabel='', ylabel='',
                 xlim=None, ylim=None, xscale='linear', yscale='linear',
                 width=4, height=3, dpi=75, hold=False, bg_color='#2D2D2D'):
        mpl_style(dark=True)
        self.figure = Figure(figsize=(width, height), dpi=dpi, facecolor=bg_color)
        # self.figure.subplots_adjust(right=0.8)

        # self.figure.colorbar()
        self.axes = self.figure.add_subplot(111)
        self.axes.set_title(title)
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        if xscale is not None:
            self.axes.set_xscale(xscale)
        if yscale is not None:
            self.axes.set_yscale(yscale)
        if xlim is not None:
            self.axes.set_xlim(*xlim)
        if ylim is not None:
            self.axes.set_ylim(*ylim)
        # self.axes.hold(hold)

        # self.axes2 = self.axes.twinx()

        Canvas.__init__(self, self.figure)
        self.setParent(parent)

        # Canvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        Canvas.updateGeometry(self)

    def sizeHint(self):
        w, h = self.get_width_height()
        return QSize(w, h)

    def minimumSizeHint(self):
        return QSize(10, 10)


# ===============================================================================
#   Example
# ===============================================================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QMainWindow, QApplication
    from numpy import linspace


    class ApplicationWindow(QMainWindow):
        def __init__(self):
            QMainWindow.__init__(self)
            self.mplwidget = MatplotlibWidget(self, title='Example',
                                              xlabel='Linear scale',
                                              ylabel='Log scale',
                                              hold=True, yscale='log')
            self.mplwidget.setFocus()
            self.setCentralWidget(self.mplwidget)

            self.plot(self.mplwidget.axes)

        def plot(self, axes):
            x = linspace(-10, 10)
            axes.tick_params(axis="y", direction="in", pad=10)
            axes.tick_params(axis="x", direction="in", pad=10)
            axes.plot(x, x ** 2, label='no 1')
            axes.plot(x, x ** 3, label='no 2')
            axes.legend(loc='upper center', bbox_to_anchor=(1.1, 1), ncol=1)


    app = QApplication(sys.argv)
    win = ApplicationWindow()
    win.show()
    app.exec()
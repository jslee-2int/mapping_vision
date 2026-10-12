import sys
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtCore import Qt
from ui_sp import Ui_MainWindow
from acton_spec_interface import ActonSpectrometer
import serial.tools.list_ports

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SpectrometerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.debug("Initializing SpectrometerGUI")
        
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Initialize spectrometer connection
        self.spectrometer = None
        self.connect_spectrometer()
        
        # Connect signals
        self.ui.setWavelengthButton.clicked.connect(self.set_wavelength)
        self.ui.readWavelengthButton.clicked.connect(self.read_wavelength)
        self.ui.setGratingButton.clicked.connect(self.set_grating)
        
        # Initial update
        self.update_status()
        
    def connect_spectrometer(self):
        try:
            logger.debug("Attempting to connect to spectrometer on COM5")
            # Connect directly to COM5
            try:
                self.spectrometer = ActonSpectrometer('COM5')
                self.ui.statusbar.showMessage("Connected to spectrometer on COM5")
                logger.info("Successfully connected to spectrometer on COM5")
                return
            except Exception as e:
                logger.error(f"Failed to connect to COM5: {str(e)}")
                self.show_error(f"Failed to connect to COM5: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error connecting to spectrometer: {str(e)}")
            self.show_error(f"Error connecting to spectrometer: {str(e)}")
            
    def set_wavelength(self):
        if not self.spectrometer:
            self.show_error("Spectrometer not connected!")
            return
            
        try:
            wavelength = self.ui.wavelengthSpinBox.value()
            logger.debug(f"Setting wavelength to {wavelength} nm")
            self.spectrometer.write_wl_fast(wavelength)
            self.update_status()
            self.ui.statusbar.showMessage(f"Wavelength set to {wavelength} nm")
            logger.info(f"Successfully set wavelength to {wavelength} nm")
        except Exception as e:
            logger.error(f"Error setting wavelength: {str(e)}")
            self.show_error(f"Error setting wavelength: {str(e)}")
            
    def read_wavelength(self):
        if not self.spectrometer:
            self.show_error("Spectrometer not connected!")
            return
            
        try:
            logger.debug("Reading current wavelength")
            wavelength = self.spectrometer.read_wl()
            self.ui.currentWavelengthLabel.setText(f"{wavelength:.3f}")
            self.ui.statusbar.showMessage(f"Current wavelength: {wavelength} nm")
            logger.info(f"Current wavelength: {wavelength} nm")
        except Exception as e:
            logger.error(f"Error reading wavelength: {str(e)}")
            self.show_error(f"Error reading wavelength: {str(e)}")
            
    def set_grating(self):
        if not self.spectrometer:
            self.show_error("Spectrometer not connected!")
            return
            
        try:
            grating = self.ui.gratingSpinBox.value()
            logger.debug(f"Setting grating to {grating}")
            self.spectrometer.write_grating(grating)
            self.update_status()
            self.ui.statusbar.showMessage(f"Grating set to {grating}")
            logger.info(f"Successfully set grating to {grating}")
        except Exception as e:
            logger.error(f"Error setting grating: {str(e)}")
            self.show_error(f"Error setting grating: {str(e)}")
            
    def update_status(self):
        if not self.spectrometer:
            return
            
        try:
            logger.debug("Updating status")
            # Update wavelength
            wavelength = self.spectrometer.read_wl()
            self.ui.currentWavelengthLabel.setText(f"{wavelength:.3f}")
            
            # Update grating
            grating = self.spectrometer.read_grating()
            grating_name = self.spectrometer.read_grating_name()
            self.ui.currentGratingLabel.setText(f"{grating} - {grating_name[1]}")
            logger.info(f"Status updated - Wavelength: {wavelength} nm, Grating: {grating}")
        except Exception as e:
            logger.error(f"Error updating status: {str(e)}")
            self.show_error(f"Error updating status: {str(e)}")
            
    def show_error(self, message):
        logger.error(message)
        QMessageBox.critical(self, "Error", message)
        self.ui.statusbar.showMessage(message)
            
    def closeEvent(self, event):
        if self.spectrometer:
            logger.debug("Closing spectrometer connection")
            self.spectrometer.close()
        event.accept()

if __name__ == '__main__':
    logger.debug("Starting application")
    app = QApplication(sys.argv)
    window = SpectrometerGUI()
    window.show()
    logger.debug("Application window shown")
    sys.exit(app.exec()) 
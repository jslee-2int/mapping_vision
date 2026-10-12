from ScopeFoundry.hardware import HardwareComponent
import numpy as np

try:
    from ref_code.HW_andor_spec.andor_spec_dev import AndorShamrockSpec
except ModuleNotFoundError:
    from andor_spec_dev import AndorShamrockSpec


class AndorShamrockSpecHW(HardwareComponent):
    
    name = 'andor_spec'
    
    def setup(self):
        
        self.settings.New('dev_id', dtype=int, initial=0)
        self.settings.New('serial_num', dtype=str, ro=True)
        
        self.settings.New('center_wl',
                                dtype=float, 
                                fmt="%1.3f",
                                ro=False,
                                unit = "nm",
                                si=False,
                                vmin=-100, vmax=2000,
                                spinbox_decimals = 3,
                                reread_from_hardware_after_write = True
                                )

        self.settings.New('turret', dtype=int, ro=True)
        self.settings.New('grating_id', dtype=int, initial=1, choices=(1,2,3,4,5,6))
        self.settings.New('grating_name', dtype=str, ro=True)
        
        self.settings.New('input_flipper', dtype=str, choices=('direct', 'side'))
        self.settings.New('output_flipper', dtype=str, choices=('direct', 'side'))
        
        self.settings.New('focus_mirror', dtype=int, unit='steps')
        
        self.settings.New('slit_input_side', dtype=float, unit='um')
        #self.settings.New('slit_output_side', dtype=float, unit='um')
        
        self.settings.New('grating_calib_side_in', dtype=float, 
                          array=True, initial=[[300e6,0,0,256,0,  (1/150.)*1e6, 16e3,0]]*4)

        self.settings.New('grating_calib_direct_in', dtype=float, 
                          array=True, initial=[[300e6,0,0,256,0,  (1/150.)*1e6, 16e3,0]]*4)

        # Detector offsets
        self.settings.New('det_offset_direct_direct', dtype=int)
        self.settings.New('det_offset_direct_side', dtype=int)
        self.settings.New('det_offset_side_direct', dtype=int)
        self.settings.New('det_offset_side_side', dtype=int)

        # grating offsets
        self.settings.New('grating_offset_1', dtype=int)
        self.settings.New('grating_offset_2', dtype=int)
        self.settings.New('grating_offset_3', dtype=int)
        self.settings.New('grating_offset_4', dtype=int)

        #calibration promt
        #self.add_operation('calibration', self.load_ui_calibration)
        
        
    def connect(self):
        S = self.settings
        
        spec = self.spec = AndorShamrockSpec(dev_id=S['dev_id'])
        
        S['serial_num'] = spec.serial_number
        S['turret'] = spec.get_turret()
        
        ## update grating list
        S.grating_id.change_choice_list(
            tuple([ ("{}: {}".format(num,name), num) 
                   for num, name in spec.gratings.items()])
            )

        S.grating_id.connect_to_hardware(
            read_func = spec.get_grating,
            write_func = spec.set_grating
            )
        
        S.grating_id.add_listener(self.on_grating_id_change)
        
        S.input_flipper.connect_to_hardware(
            read_func = lambda flipper='input': spec.get_flipper_mirror(flipper), 
            write_func = lambda port, flipper='input': spec.set_flipper_mirror(flipper, port), 
            )
        
        S.output_flipper.connect_to_hardware(
            read_func = lambda flipper='output': spec.get_flipper_mirror(flipper), 
            write_func = lambda port, flipper='output': spec.set_flipper_mirror(flipper, port), 
            )
        
        S.focus_mirror.connect_to_hardware(
            read_func = spec.get_focus_mirror_position,
            write_func = spec.set_focus_mirror_position_abs)
        
        S.slit_input_side.connect_to_hardware(
            read_func = lambda slit='input_side': spec.get_slit_width(slit),
            write_func = lambda w, slit='input_side': spec.set_slit_width(slit, w)
            )
        
        S.center_wl.connect_to_hardware(
            read_func = spec.get_wavelength,
            write_func = spec.set_wavelength)

        S.det_offset_direct_direct.connect_to_hardware(
            read_func = lambda: spec.get_detector_offset('direct', 'direct'),
            write_func = lambda x: spec.set_detector_offset('direct', 'direct', x)
        )
        S.det_offset_direct_side.connect_to_hardware(
            read_func = lambda: spec.get_detector_offset('direct', 'side'),
            write_func = lambda x: spec.set_detector_offset('direct', 'side', x)
        )
        S.det_offset_direct_direct.connect_to_hardware(
            read_func = lambda: spec.get_detector_offset('side', 'direct'),
            write_func = lambda x: spec.set_detector_offset('side', 'direct', x)
        )
        S.det_offset_side_side.connect_to_hardware(
            read_func = lambda: spec.get_detector_offset('side', 'side'),
            write_func = lambda x: spec.set_detector_offset('side', 'side', x)
        )                        




        S.grating_offset_1.connect_to_hardware(
            read_func = lambda: spec.get_grating_offset(1),
            write_func = lambda x: spec.set_grating_offset(1,x)
        )
        S.grating_offset_2.connect_to_hardware(
            read_func = lambda: spec.get_grating_offset(2),
            write_func = lambda x: spec.set_grating_offset(2,x)
        )
        S.grating_offset_3.connect_to_hardware(
            read_func = lambda: spec.get_grating_offset(3),
            write_func = lambda x: spec.set_grating_offset(3,x)
        )
        S.grating_offset_4.connect_to_hardware(
            read_func = lambda: spec.get_grating_offset(4),
            write_func = lambda x: spec.set_grating_offset(4,x)
        )


        self.read_from_hardware()
        self.on_grating_id_change()
        
    def disconnect(self):
        
        self.settings.disconnect_all_from_hardware()
        
        if hasattr(self, "spec"):
            self.spec.close()
            del self.spec
        
        
        
    def on_grating_id_change(self):
        self.settings['grating_name'] = self.spec.gratings[self.settings['grating_id']]
        self.settings.focus_mirror.read_from_hardware()
    '''     
    def load_ui_calibration(self):
        self.ui=load_qt_ui_file('C:\\Users\\lab\\Documents\\foundry_scope\mi_cryo_micro\\montana_setup_control.ui')    
        self.ui.show()
        self.ui.activateWindow()
    '''
       
    def get_wl_calibration(self, px_index, binning=1, m_order=1):
        S = self.settings
        grating_id = S['grating_id'] - 1
        
        
        if S['input_flipper'] == 'side':
            grating_calib_array = S['grating_calib_side_in'][grating_id]
        if S['input_flipper'] == 'direct':
            grating_calib_array = S['grating_calib_direct_in'][grating_id] 
        f, delta, gamma, n0, offset_adjust, d_grating, x_pixel  = grating_calib_array[0:7]
        curvature = 0
        if len(grating_calib_array) > 7:
            curvature = grating_calib_array[7]
        binned_px = binning*px_index + 0.5*(binning-1)
        wl = wl_p_calib(binned_px, n0, offset_adjust, S['center_wl'], m_order, d_grating, x_pixel, f, delta, gamma, curvature)
        
        #print('get_wl_calibration', 'grating#', grating_id, 'grating calib:', S['grating_calibrations'][grating_id], 'center wl:', S['center_wl'], 'output:', wl)
        
        return wl
        
def wl_p_calib(px, n0, offset_adjust, wl_center, m_order, d_grating, x_pixel, f, delta, gamma, curvature=0):
    #print('wl_p_calib:', px, n0, offset_adjust, wl_center, m_order, d_grating, x_pixel, f, delta, gamma, curvature)
    #consts
    #d_grating = 1./150. #mm
    #x_pixel   = 16e-3 # mm
    #m_order   = 1 # diffraction order, unitless
    n = px - (n0+offset_adjust*wl_center)

    #print('psi top', m_order* wl_center)
    #print('psi bottom', (2*d_grating*np.cos(gamma/2)) )

    psi = np.arcsin( m_order* wl_center / (2*d_grating*np.cos(gamma/2)))
    eta = np.arctan(n*x_pixel*np.cos(delta) / (f+n*x_pixel*np.sin(delta)))

    return ((d_grating/m_order)
                    *(np.sin(psi-0.5*gamma)
                      + np.sin(psi+0.5*gamma+eta))) + curvature*n**2


if __name__ == "__main__":
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(
        description="AndorShamrockSpecHW: quick calibration math test or Shamrock connect test.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="wl_p_calib만 실행 (DLL/스펙트로미터 없음)",
    )
    parser.add_argument(
        "--dev-id",
        type=int,
        default=0,
        metavar="N",
        help="Shamrock 장치 인덱스 (connect 테스트 시)",
    )
    args = parser.parse_args()

    if args.quick:
        # 대표 파라미터로 파장 보정식이 유한값을 내는지 확인
        px, n0, off, wl_c = 128.0, 256.0, 0.0, 532.0
        m_order, d_g, x_pix = 1, (1 / 150.0) * 1e6, 16e3
        f, delta, gamma = 300e6, 0.0, 0.0
        wl = wl_p_calib(px, n0, off, wl_c, m_order, d_g, x_pix, f, delta, gamma)
        print("wl_p_calib quick check:", wl, "nm")
        sys.exit(0)

    # ScopeFoundry HardwareComponent는 QObject + event_filter가 있는 app이 필요함
    os.environ.setdefault("QT_API", "pyqt6")
    os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

    from qtpy.QtWidgets import QApplication

    class _MinimalScopeApp:
        event_filter = None

        def launch_browser(self, *_a, **_kw):
            pass

    qapp = QApplication.instance() or QApplication(sys.argv)
    hw = AndorShamrockSpecHW(_MinimalScopeApp())
    hw.settings["dev_id"] = args.dev_id
    try:
        hw.connect()
        print("connected: serial_num =", hw.settings["serial_num"])
        print("  turret =", hw.settings["turret"])
        print("  grating_id =", hw.settings["grating_id"], "|", hw.settings["grating_name"])
        print("  center_wl (nm) =", hw.settings["center_wl"])
    finally:
        if hasattr(hw, "spec"):
            hw.disconnect()


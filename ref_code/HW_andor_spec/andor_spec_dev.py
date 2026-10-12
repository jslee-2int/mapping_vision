import os
import sys
from ctypes import c_int, c_uint, c_byte, c_ubyte, c_short, c_double, c_float, c_long
from ctypes import pointer, byref, windll, cdll, create_string_buffer
from ctypes import POINTER, c_char_p

# 환경 변수로 재정의 가능 (끝에 \ 없이)
DEFAULT_SHAMROCK_SDK_DIR = r"C:\Program Files\Andor SDK\Shamrock64"


def _shamrock_sdk_dir():
    return os.environ.get("ANDOR_SHAMROCK_SDK", DEFAULT_SHAMROCK_SDK_DIR)


def _prepare_shamrock_dll_search_path(sdk_dir):
    """
    Windows Python 3.8+ 는 LoadLibrary 시 동일 폴더의 의존 DLL을 기본 검색하지 않을 수 있음.
    ShamrockCIF / atshamrock 이 Shamrock64 안의 다른 DLL을 쓰므로 경로를 등록한다.
    """
    if sys.platform != "win32":
        return
    if not os.path.isdir(sdk_dir):
        return
    # PATH: 일부 Andor DLL이 로더 검색 시 PATH를 참고
    sep = ";" if sys.platform == "win32" else ":"
    path = os.environ.get("PATH", "")
    if sdk_dir not in path.split(sep):
        os.environ["PATH"] = sdk_dir + sep + path
    add = getattr(os, "add_dll_directory", None)
    if add is not None:
        add(sdk_dir)


def _candidate_andor_dll_dirs():
    """Solis/SDK2 쪽 atmcd*.dll 등이 있을 수 있는 폴더(존재하는 것만)."""
    env = os.environ.get("ANDOR_SDK2_DIR")
    candidates = [
        env,
        r"C:\Program Files\Andor SDK\bin",
        r"C:\Program Files\Andor SDK",
        r"C:\Program Files\Andor SOLIS",
        r"C:\Program Files\Andor SOLIS\Shamrock",
        r"C:\Program Files\Andor\User Software\SDK",
    ]
    seen = set()
    out = []
    for d in candidates:
        if not d or d in seen:
            continue
        seen.add(d)
        if os.path.isdir(d):
            out.append(d)
    return out


def _prepare_andor_dll_paths_for_shamrock(shamrock_dir):
    """Shamrock64 + (가능하면) SDK2/Solis 경로를 DLL 검색에 넣는다."""
    _prepare_shamrock_dll_search_path(shamrock_dir)
    for d in _candidate_andor_dll_dirs():
        if os.path.normcase(d) != os.path.normcase(shamrock_dir):
            _prepare_shamrock_dll_search_path(d)


SHAMROCK_COMMUNICATION_ERROR = 20201
SHAMROCK_SUCCESS = 20202
SHAMROCK_P1INVALID = 20266
SHAMROCK_P2INVALID = 20267
SHAMROCK_P3INVALID = 20268
SHAMROCK_P4INVALID = 20269
SHAMROCK_P5INVALID = 20270
SHAMROCK_NOT_INITIALIZED = 20275
SHAMROCK_NOT_AVAILABLE = 20292

SHAMROCK_ACCESSORYMIN = 0
SHAMROCK_ACCESSORYMAX = 1
SHAMROCK_FILTERMIN = 1
SHAMROCK_FILTERMAX = 6
SHAMROCK_TURRETMIN = 1
SHAMROCK_TURRETMAX = 3
SHAMROCK_GRATINGMIN = 1
SHAMROCK_SLITWIDTHMIN = 10
SHAMROCK_SLITWIDTHMAX = 2500
SHAMROCK_I24SLITWIDTHMAX = 24000
SHAMROCK_SHUTTERMODEMIN = 0
SHAMROCK_SHUTTERMODEMAX = 1
SHAMROCK_DET_OFFSET_MIN = -240000
SHAMROCK_DET_OFFSET_MAX = 240000
SHAMROCK_GRAT_OFFSET_MIN = -20000
SHAMROCK_GRAT_OFFSET_MAX = 20000

SHAMROCK_SLIT_INDEX_MIN  = 1
SHAMROCK_SLIT_INDEX_MAX  = 4

SHAMROCK_INPUT_SLIT_SIDE  = 1
SHAMROCK_INPUT_SLIT_DIRECT  = 2
SHAMROCK_OUTPUT_SLIT_SIDE  = 3
SHAMROCK_OUTPUT_SLIT_DIRECT = 4

SHAMROCK_FLIPPER_INDEX_MIN  = 1
SHAMROCK_FLIPPER_INDEX_MAX  = 2
SHAMROCK_PORTMIN = 0
SHAMROCK_PORTMAX = 1

SHAMROCK_INPUT_FLIPPER   = 1
SHAMROCK_OUTPUT_FLIPPER = 2
SHAMROCK_DIRECT_PORT = 0
SHAMROCK_SIDE_PORT = 1

SHAMROCK_ERRORLENGTH = 64

consts_by_num = dict()
for name,num in list(locals().items()):
    if name.startswith("SHAMROCK_"):
        consts_by_num[num] = name
        
        
def _err(retval):
    if retval == SHAMROCK_SUCCESS:
        return retval
    else:
        err_name = consts_by_num.get(retval)
        raise IOError( "Andor SHAMROCK Failure {}: {}".format(retval, err_name))


def _bind_shamrock_cif_prototypes(lib):
    """ctypes argtypes 미설정 시 byref(포인터) 호출이 깨져 SHAMROCK_P1INVALID 등이 날 수 있음 (ShamrockCIF.h)."""
    lib.ShamrockInitialize.argtypes = [c_char_p]
    lib.ShamrockInitialize.restype = c_uint
    lib.ShamrockClose.argtypes = []
    lib.ShamrockClose.restype = c_uint
    lib.ShamrockGetNumberDevices.argtypes = [POINTER(c_int)]
    lib.ShamrockGetNumberDevices.restype = c_uint
    lib.ShamrockGetSerialNumber.argtypes = [c_int, c_char_p]
    lib.ShamrockGetSerialNumber.restype = c_uint
    lib.ShamrockEepromGetOpticalParams.argtypes = [
        c_int,
        POINTER(c_float),
        POINTER(c_float),
        POINTER(c_float),
    ]
    lib.ShamrockEepromGetOpticalParams.restype = c_uint
    lib.ShamrockGetNumberGratings.argtypes = [c_int, POINTER(c_int)]
    lib.ShamrockGetNumberGratings.restype = c_uint
    lib.ShamrockGetGratingInfo.argtypes = [
        c_int,
        c_int,
        POINTER(c_float),
        c_char_p,
        POINTER(c_int),
        POINTER(c_int),
    ]
    lib.ShamrockGetGratingInfo.restype = c_uint
    lib.ShamrockAutoSlitIsPresent.argtypes = [c_int, c_int, POINTER(c_int)]
    lib.ShamrockAutoSlitIsPresent.restype = c_uint
    lib.ShamrockGetFocusMirrorMaxSteps.argtypes = [c_int, POINTER(c_int)]
    lib.ShamrockGetFocusMirrorMaxSteps.restype = c_uint
    lib.ShamrockFlipperMirrorIsPresent.argtypes = [c_int, c_int, POINTER(c_int)]
    lib.ShamrockFlipperMirrorIsPresent.restype = c_uint
    lib.ShamrockGetTurret.argtypes = [c_int, POINTER(c_int)]
    lib.ShamrockGetTurret.restype = c_uint
    lib.ShamrockGetGrating.argtypes = [c_int, POINTER(c_int)]
    lib.ShamrockGetGrating.restype = c_uint
    lib.ShamrockSetGrating.argtypes = [c_int, c_int]
    lib.ShamrockSetGrating.restype = c_uint
    lib.ShamrockGetGratingOffset.argtypes = [c_int, c_int, POINTER(c_int)]
    lib.ShamrockGetGratingOffset.restype = c_uint
    lib.ShamrockSetGratingOffset.argtypes = [c_int, c_int, c_int]
    lib.ShamrockSetGratingOffset.restype = c_uint
    lib.ShamrockGetDetectorOffsetEx.argtypes = [c_int, c_int, c_int, POINTER(c_int)]
    lib.ShamrockGetDetectorOffsetEx.restype = c_uint
    lib.ShamrockSetDetectorOffsetEx.argtypes = [c_int, c_int, c_int, c_int]
    lib.ShamrockSetDetectorOffsetEx.restype = c_uint
    lib.ShamrockGetWavelength.argtypes = [c_int, POINTER(c_float)]
    lib.ShamrockGetWavelength.restype = c_uint
    lib.ShamrockSetWavelength.argtypes = [c_int, c_float]
    lib.ShamrockSetWavelength.restype = c_uint
    lib.ShamrockGetAutoSlitWidth.argtypes = [c_int, c_int, POINTER(c_float)]
    lib.ShamrockGetAutoSlitWidth.restype = c_uint
    lib.ShamrockSetAutoSlitWidth.argtypes = [c_int, c_int, c_float]
    lib.ShamrockSetAutoSlitWidth.restype = c_uint
    lib.ShamrockGetFocusMirror.argtypes = [c_int, POINTER(c_int)]
    lib.ShamrockGetFocusMirror.restype = c_uint
    lib.ShamrockSetFocusMirror.argtypes = [c_int, c_int]
    lib.ShamrockSetFocusMirror.restype = c_uint
    lib.ShamrockGetFlipperMirror.argtypes = [c_int, c_int, POINTER(c_int)]
    lib.ShamrockGetFlipperMirror.restype = c_uint
    lib.ShamrockSetFlipperMirror.argtypes = [c_int, c_int, c_int]
    lib.ShamrockSetFlipperMirror.restype = c_uint


class AndorShamrockSpec(object):
    
    def __init__(self, dev_id=0):
        self.dev_id = dev_id

        sdk_dir = _shamrock_sdk_dir()
        _prepare_andor_dll_paths_for_shamrock(sdk_dir)
        atshamrock = os.path.join(sdk_dir, "atshamrock.dll")
        shamrock_cif = os.path.join(sdk_dir, "ShamrockCIF.dll")

        self.lib0 = windll.LoadLibrary(atshamrock)
        lib = self.lib = windll.LoadLibrary(shamrock_cif)
        _bind_shamrock_cif_prototypes(lib)

        _err(lib.ShamrockInitialize(b""))
        
        n_dev = c_int()
        _err(lib.ShamrockGetNumberDevices(byref(n_dev)))
        n = n_dev.value

        print("Found {} Andor Shamrock Spectrometers".format(n))

        if n == 0:
            lib.ShamrockClose()
            hints = [
                "Solis를 완전히 종료한 뒤 다시 시도(다른 프로세스가 장치를 점유하면 0대로 나올 수 있음).",
                "스펙트로그래프가 카메라 뒤 I2C로만 붙는 구성이면, Shamrock API만 호출해서는 0대가 될 수 있습니다. "
                "Andor SDK2로 카메라를 먼저 연 다음 Shamrock을 여는 흐름이 필요합니다 "
                "(pylablib: AndorSDK2Camera 후 ShamrockSpectrograph; 문서: Andor Shamrock spectrometers).",
                "독립 USB Shamrock이면 USB·전원·장치 관리자를 확인.",
                "Shamrock DLL: ANDOR_SHAMROCK_SDK={!r}; SDK2/Solis DLL 폴더는 ANDOR_SDK2_DIR 또는 자동 후보 경로에 추가됨.".format(
                    sdk_dir
                ),
            ]
            raise IOError(
                "인식된 Shamrock 스펙트로미터가 없습니다. "
                + " ".join(hints)
            )
        if dev_id < 0 or dev_id >= n:
            lib.ShamrockClose()
            raise IOError(
                "dev_id={} 는 유효하지 않습니다(연결된 장치 수 {}).".format(dev_id, n)
            )

        # Serial Number
        x = create_string_buffer(64)
        _err(lib.ShamrockGetSerialNumber(dev_id,x))
        self.serial_number = x.value.decode()
        
        # EEPROM parameters
        f = c_float()
        ang = c_float()
        tilt = c_float()
        
        _err(lib.ShamrockEepromGetOpticalParams(dev_id, byref(f), byref(ang), byref(tilt)))

        self.focal_length = f.value
        self.angular_deviation = ang.value
        self.focal_tilt = tilt.value
        
        # gratings
        x = c_int()
        _err(lib.ShamrockGetNumberGratings(dev_id, byref(x)))
        self.num_gratings = x.value
        
        self.gratings = dict()
        for i in range(1, self.num_gratings+1):
            lines, blaze, home, offset = self.get_grating_info(i)
            self.gratings[i] = "{:1.0f}g/mm {}".format(lines, blaze)
        
        # Slits
        self.slit_ids = dict(
            input_side = 1,
            input_direct = 2,
            ouput_side = 3,
            output_direct = 4)

        self.slit_present = dict()
        
        for name, num in self.slit_ids.items():
            x = c_int()
            _err(lib.ShamrockAutoSlitIsPresent(dev_id, num, byref(x)))
            self.slit_present[name] = bool(x.value)
            
        # Focus mirror
        x = c_int()
        ## Gets maximum possible focus position in steps
        _err(lib.ShamrockGetFocusMirrorMaxSteps(dev_id, byref(x)))
        self.focus_mirror_max_steps = x.value
        
        # Flipper mirrors
        self.flipper_mirror_ids = dict(
            input = 1,
            output = 2,
            )
        self.flipper_mirror_present = dict()
        for name, num in self.flipper_mirror_ids.items():
            x = c_int()
            _err(lib.ShamrockFlipperMirrorIsPresent(dev_id, num, byref(x)))
            self.flipper_mirror_present[name] = bool(x.value)

        
         
        
    
    def close(self):
        self.lib.ShamrockClose()
        
    def get_turret(self):
        x = c_int()
        _err(self.lib.ShamrockGetTurret(self.dev_id, byref(x)))
        self.turret_num = x.value
        return self.turret_num
    
    ### Grating
    
    def get_grating(self):
        x = c_int()
        _err(self.lib.ShamrockGetGrating(self.dev_id, byref(x)))
        self.grating_num = x.value
        return self.grating_num
    
    def set_grating(self, grating_id):
        _err(self.lib.ShamrockSetGrating(self.dev_id, int(grating_id)))
    
    def get_grating_info(self, grating_num):
        lines = c_float()
        blaze = create_string_buffer(64)
        home = c_int()
        offset = c_int()
        _err(self.lib.ShamrockGetGratingInfo(self.dev_id, grating_num, 
                                             byref(lines), blaze, byref(home), byref(offset)))
        
        return(lines.value, blaze.value.decode(), home.value, offset.value)


    def get_grating_offset(self, grating_id):
        """
        unsigned int WINAPI ShamrockGetGratingOffset(int device,int grating, int *offset)
 
        Description
        Returns the grating offset
 
        """
        offset = c_int()
        _err(self.lib.ShamrockGetGratingOffset(self.dev_id, grating_id, byref(offset)))
        return offset.value

    def set_grating_offset(self, grating_id, offset):
        _err(self.lib.ShamrockSetGratingOffset(self.dev_id, grating_id, offset))


    ### Detector Offset

    def get_detector_offset(self, entrance, exit):
        """
        entrance and exit are either 'direct' or 'side'

        unsigned int WINAPI ShamrockGetDetectorOffsetEx(int device, int entrancePort, int exitPort, int *offset)
    
        Description
        Sets the detector offset. Use this function if the system has 4 ports and a detector offset value of a specific entrance and exit port combination is required.
        
        Combinations
        DIRECT, DIRECT = 0, 0
        DIRECT, SIDE      = 0, 1
        SIDE, DIRECT      = 1, 0
        SIDE, SIDE           = 1, 1
        
        Parameters
        int device: Shamrock to interrogate
        int entrancePort: Select entrance port to use
        int exitPort: Select exit port to use
        int *offset: pointer to detector offset (steps)
        """
        E = {'direct':0, 'side':1}
        offset = c_int()
        _err(self.lib.ShamrockGetDetectorOffsetEx(self.dev_id, E[entrance], E[exit], byref(offset)))
        return offset.value

    def set_detector_offset(self, entrance, exit, offset):
        """
        entrance and exit are either 'direct' or 'side'

        unsigned int WINAPI ShamrockSetDetectorOffsetEx(int device, int entrancePort, int exitPort, int offset)
 
        Description
        Sets the detector offset. Use this function if the system has 4 ports and a detector offset for a specific entrance and exit port combination is to be set.
        
        Combinations
        DIRECT, DIRECT = 0, 0
        DIRECT, SIDE      = 0, 1
        SIDE, DIRECT      = 1, 0
        SIDE, SIDE           = 1, 1
        
        Parameters
        int device: Select Shamrock to control
        int entrancePort: Select entrance port to use
        int exitPort: Select exit port to use
        int offset: detector offset (steps)
        """
        E = {'direct':0, 'side':1}
        offset = c_int(offset)
        _err(self.lib.ShamrockSetDetectorOffsetEx(self.dev_id, E[entrance], E[exit], offset))



    ### Wavelength
        
    def get_wavelength(self):
        x = c_float()
        _err(self.lib.ShamrockGetWavelength(self.dev_id, byref(x)))
        self.wavelength = x.value
        return self.wavelength
    
    def set_wavelength(self, wl):
        _err(self.lib.ShamrockSetWavelength(self.dev_id, c_float(wl)))
        
    ### Slits
    
    def get_slit_width(self, slit):
        s_id = self.slit_ids[slit]
        x = c_float()
        _err(self.lib.ShamrockGetAutoSlitWidth(self.dev_id, s_id, byref(x)))
        return x.value
    
    def set_slit_width(self, slit, width):
        s_id = self.slit_ids[slit]
        _err(self.lib.ShamrockSetAutoSlitWidth(self.dev_id, s_id, c_float(width)))

    
    ### Focus Mirror
    
    def get_focus_mirror_position(self):
        x = c_int()
        _err(self.lib.ShamrockGetFocusMirror(self.dev_id, byref(x)))
        self.focus_mirror_position = x.value
        return self.focus_mirror_position
    
    def set_focus_mirror_position_rel(self, delta):
        """
        Relative Focus Mirror motion
        Sets the required Focus movement. Focus movement is possible
        from 0 to max steps, so possible values will be from
        (0 - current steps) to (max - current steps).
        +steps move focus mirror forward
        -steps move focus mirror backwards
        """
        _err(self.lib.ShamrockSetFocusMirror(self.dev_id, int(delta)))
        
    def set_focus_mirror_position_abs(self, pos):
        assert 0 <= pos <= self.focus_mirror_max_steps # might be < instead of <=
        current_pos = self.get_focus_mirror_position()
        delta = int(pos) - current_pos
        self.set_focus_mirror_position_rel(delta)
        
    ### Flipper Mirror
    
    def get_flipper_mirror(self, flipper):
        m_id = self.flipper_mirror_ids[flipper]
        
        x = c_int()
        _err(self.lib.ShamrockGetFlipperMirror(self.dev_id, m_id, byref(x)))
        #print('mirror', m_id, x.value)

        flipper_positions = {0: 'direct', 1:'side'}
        return flipper_positions[x.value]
        
        #_err(self.lib.ShamrockGetFlipperMirrorPosition(self.dev_id, m_id, byref(x)))
        #print('pos', m_id, x.value)
        #_err(self.lib.ShamrockGetFlipperMirrorMaxPosition(self.dev_id, m_id, byref(x)))
        #print('max', x.value)
        
        
    def set_flipper_mirror(self, flipper, port):
        assert self.flipper_mirror_present[flipper]
        m_id = self.flipper_mirror_ids[flipper]
        flipper_position_ids = {'direct':0, 'side':1}
        pos_id = flipper_position_ids[port]
        _err(self.lib.ShamrockSetFlipperMirror(self.dev_id, m_id, pos_id))

        
        
# test code
if __name__ == '__main__':
    
    s = AndorShamrockSpec()
    try:
        print("serial_number", s.serial_number)
        print("focal_length", s.focal_length)
        print("angular_deviation", s.angular_deviation)
        print("focal_tilt", s.focal_tilt)

        print("turret", s.get_turret())
        print("grating", s.get_grating())
        for i in range(4):
            print("grating_info", i+1, s.get_grating_info(i+1))
            print("grating offset", i+1, s.get_grating_offset(i+1))
        print(s.gratings)
        print("wl", s.get_wavelength())
        
        print("focus_mirror", s.get_focus_mirror_position())
        #s.set_focus_mirror_position_abs(261)
        #print("focus_mirror", s.get_focus_mirror_position())

        print("Slits", s.slit_present)
        
        print("Flipper Mirror", s.flipper_mirror_present)
        print("-->input", s.get_flipper_mirror('input'))
        print("-->output", s.get_flipper_mirror('output'))

        for x in ['direct', 'side']:
            for y in ['direct', 'side']:
                print('detector offset {} {}: {}'.format(x, y, s.get_detector_offset(x,y)))
        
#         print("-->input", s.get_flipper_mirror('input'))
#         print("move to direct")
#         s.set_flipper_mirror('input', 'direct')
#         print("-->input", s.get_flipper_mirror('input'))
#         print("move to side")
#         s.set_flipper_mirror('input', 'side')
#         print("-->input", s.get_flipper_mirror('input'))
        
        
    finally:
        s.close()
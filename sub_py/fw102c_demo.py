"""
FilterWheel102 Demo - Python version
Converted from Fw102C_Demo.cpp
"""

import ctypes
from ctypes import c_char_p, c_int, byref, POINTER
import sys
import os


class FilterWheel102C:
    """Python wrapper for FilterWheel102_win32.dll"""
    
    def __init__(self):
        self.hdll = None
        self.pcount = 0
        
        # Function pointers
        self.GetPorts = None
        self.Open = None
        self.Close = None
        self.GetPosition = None
        self.GetTrigMode = None
        self.GetPositionCount = None
        self.SetPosition = None
        self.SetTriggerMode = None
    
    def init(self):
        """Initialize DLL and load functions"""
        try:
            # Load DLL
            dll_path = "./msvc/FilterWheel102_win32.dll"
            self.hdll = ctypes.WinDLL(dll_path)
        except Exception as e:
            print(f"Failed to load FilterWheel102_win32.dll: {e}")
            print("Please check if the DLL file exists in the current directory or system path")
            return -1
        
        try:
            # Load functions from DLL
            # int GetPorts(char *serialNo)
            self.GetPorts = self.hdll.GetPorts
            self.GetPorts.argtypes = [c_char_p]
            self.GetPorts.restype = c_int
            
            # int Open(char* serialNo, int nBaud, int timeout)
            self.Open = self.hdll.Open
            self.Open.argtypes = [c_char_p, c_int, c_int]
            self.Open.restype = c_int
            
            # int Close(int hdl)
            self.Close = self.hdll.Close
            self.Close.argtypes = [c_int]
            self.Close.restype = c_int
            
            # int GetPosition(int hdl, int& pos)
            self.GetPosition = self.hdll.GetPosition
            self.GetPosition.argtypes = [c_int, POINTER(c_int)]
            self.GetPosition.restype = c_int
            
            # int GetTriggerMode(int hdl, int& triggermode)
            self.GetTrigMode = self.hdll.GetTriggerMode
            self.GetTrigMode.argtypes = [c_int, POINTER(c_int)]
            self.GetTrigMode.restype = c_int
            
            # int GetPositionCount(int hdl, int& poscount)
            self.GetPositionCount = self.hdll.GetPositionCount
            self.GetPositionCount.argtypes = [c_int, POINTER(c_int)]
            self.GetPositionCount.restype = c_int
            
            # int SetPosition(int hdl, int pos)
            self.SetPosition = self.hdll.SetPosition
            self.SetPosition.argtypes = [c_int, c_int]
            self.SetPosition.restype = c_int
            
            # int SetTriggerMode(int hdl, int mode)
            self.SetTriggerMode = self.hdll.SetTriggerMode
            self.SetTriggerMode.argtypes = [c_int, c_int]
            self.SetTriggerMode.restype = c_int
            
        except Exception as e:
            print(f"Failed to load functions from DLL: {e}")
            return -1
        
        return 0
    
    def get_pos(self, hdl):
        """Get current position"""
        value = c_int(-1)
        ret = self.GetPosition(hdl, byref(value))
        if ret == 0:
            print(f"current position: {value.value}.")
        return value.value if ret == 0 else -1
    
    def set_pos(self, hdl, pos):
        """Set position"""
        if pos <= 0 or pos > self.pcount:
            print(f"position is invalid, current position count is {self.pcount}")
            return
        
        ret = self.SetPosition(hdl, pos)
        if ret == 0:
            print("set position success")
        else:
            print("set position failed")
    
    def get_trigger_mode(self, hdl):
        """Get trigger mode"""
        value = c_int(-1)
        ret = self.GetTrigMode(hdl, byref(value))
        if ret == 0:
            print(f"current trigger mode: {value.value}.")
        return value.value if ret == 0 else -1
    
    def set_trigger_mode(self, hdl, mode):
        """Set trigger mode"""
        ret = self.SetTriggerMode(hdl, mode)
        if ret == 0:
            print("set trigger mode success")
        else:
            print("set trigger mode failed")


def main():
    """Main function"""
    fw = FilterWheel102C()
    
    # Initialize DLL
    if fw.init() < 0:
        return 0
    
    # Get COM port
    sn_buffer = ctypes.create_string_buffer(256)
    fw.GetPorts(sn_buffer)
    
    # Extract first port (before comma)
    sn_str = sn_buffer.value.decode('utf-8')
    if ',' in sn_str:
        sn_str = sn_str.split(',')[0]
    
    print(f"com port : {sn_str}.")
    
    # Open port
    sn_bytes = sn_str.encode('utf-8')
    hdl = fw.Open(sn_bytes, 115200, 10)
    
    if hdl < 0:
        print("com port fails, please check the driver installed correctly")
        return 0
    
    # Get position count
    pcount = c_int(0)
    fw.GetPositionCount(hdl, byref(pcount))
    fw.pcount = pcount.value
    
    # Main loop
    print("0: get position\t1: set position\t2: get trigger mode\t3: set trigger mode (press 'x' to quit)")
    
    while True:
        print("please select to continue:")
        try:
            user_input = input().strip()
            
            if not user_input:
                continue
            
            if user_input == 'x':
                break
            
            elif user_input == '0':
                fw.get_pos(hdl)
            
            elif user_input == '1':
                print("input position:")
                try:
                    pos_str = input().strip()
                    pos_value = int(pos_str)
                    fw.set_pos(hdl, pos_value)
                except ValueError:
                    print("invalid input, please input a number")
            
            elif user_input == '2':
                fw.get_trigger_mode(hdl)
            
            elif user_input == '3':
                print("input trigger mode(0 or 1):")
                mode_str = input().strip()
                if mode_str in ['0', '1']:
                    mode_value = int(mode_str)
                    fw.set_trigger_mode(hdl, mode_value)
                else:
                    print("invalid input, please input again")
            
            else:
                print("invalid option")
        
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    # Close port
    fw.Close(hdl)
    print("Port closed successfully")
    return 0


if __name__ == "__main__":
    main()


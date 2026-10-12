#!/usr/bin/env python

import time
from pylablib.devices import Thorlabs

class Thorlabs_MFF101:
    def __init__(self, serial_number="37008653", debug_mode=False):
        """Initialize with serial number and debug mode"""
        self.serial = serial_number
        self.device = None
        self._connected = False
        self.debug_mode = debug_mode
        
    def debug_print(self, message):
        """Print message only if debug mode is enabled"""
        if self.debug_mode:
            print(message)
        
    def _connect_device(self):
        """Connect to the device if not already connected"""
        if self._connected and self.device:
            return True
            
        try:
            self.device = Thorlabs.MFF(self.serial)
            self._connected = True
            return True
        except Exception as e:
            self.debug_print(f"Error connecting to device: {e}")
            self._connected = False
            return False
            
    def _disconnect_device(self):
        """Disconnect from the device"""
        if self.device and self._connected:
            try:
                self.device.close()
                self.device = None
                self._connected = False
            except:
                pass

    def _ensure_connected(self):
        """Ensure device is connected, reconnect if needed"""
        if not self._connected or not self.device:
            return self._connect_device()
        return True

    def mirror(self, switch):
        """Switch 'on' or 'off' - Optimized version"""
        if not self._ensure_connected():
            return False

        try:
            if switch == 'on':
                self.debug_print("MIRROR UP")
                self.device.move_to_state(1)
            else:
                self.debug_print("MIRROR DOWN")
                self.device.move_to_state(0)
            return True
        except Exception as e:
            self.debug_print(f"Error sending command: {e}")
            # Try to reconnect on error
            self._connected = False
            return False

    def move_to_position(self, position):
        """Move to specific position
        Args:
            position: 'up', 'down', 0, or 1
        """
        if position in ['up', 1]:
            return self.mirror('on')
        elif position in ['down', 0]:
            return self.mirror('off')
        else:
            self.debug_print(f"Invalid position: {position}")
            return False

    def get_position(self):
        """Get current position - Optimized version"""
        if not self._ensure_connected():
            return None
            
        try:
            position = self.device.get_state()
            return position
        except Exception as e:
            self.debug_print(f"Error getting position: {e}")
            # Try to reconnect on error
            self._connected = False
            return None

    def is_connected(self):
        """Check if device is connected and responding"""
        if not self._ensure_connected():
            return False
            
        try:
            # Test communication by getting state
            self.device.get_state()
            return True
        except:
            self._connected = False
            return False

    def get_device_info(self):
        """Get device information"""
        if not self._ensure_connected():
            return None
            
        try:
            info = self.device.get_device_info()
            return {
                'serial': self.serial,
                'model': info.model_no if hasattr(info, 'model_no') else 'Unknown',
                'firmware': info.fw_ver if hasattr(info, 'fw_ver') else 'Unknown'
            }
        except Exception as e:
            self.debug_print(f"Error getting device info: {e}")
            self._connected = False
            return None

    def toggle_position(self):
        """Toggle between up and down positions"""
        current_pos = self.get_position()
        if current_pos == 1:
            return self.mirror('off')
        elif current_pos == 0:
            return self.mirror('on')
        else:
            # If unknown, default to up
            return self.mirror('on')

    def toggle(self):
        """Simple toggle function - switch to opposite position"""
        current_pos = self.get_position()
        self.debug_print(f"Current position: {current_pos}")
        
        if current_pos == 1:
            self.debug_print("Toggling to position 0 (down)")
            return self.mirror('off')
        elif current_pos == 0:
            self.debug_print("Toggling to position 1 (up)")
            return self.mirror('on')
        else:
            self.debug_print("Unknown position, moving to position 1 (up)")
            return self.mirror('on')

    def get_current_position_name(self):
        """Get current position as readable name"""
        current_pos = self.get_position()
        if current_pos == 1:
            return "UP"
        elif current_pos == 0:
            return "DOWN"
        else:
            return "UNKNOWN"

    def move_to_opposite(self):
        """Move to the opposite of current position"""
        current_pos = self.get_position()
        if current_pos == 1:
            return self.move_to_position(0)
        elif current_pos == 0:
            return self.move_to_position(1)
        else:
            return self.move_to_position(1)  # Default to up

    def move_and_wait(self, position, wait_time=0.5):
        """Move to position and wait for completion - Reduced wait time"""
        success = self.move_to_position(position)
        if success:
            time.sleep(wait_time)  # Reduced from 2.0 to 0.5 seconds
        return success

    def cycle_test(self, cycles=3):
        """Test cycling between positions"""
        self.debug_print(f"Starting {cycles} cycles of position testing...")
        
        for i in range(cycles):
            self.debug_print(f"Cycle {i+1}:")
            
            # Move to position 1 (up)
            self.debug_print("  Moving to position 1 (up)...")
            if self.move_and_wait(1, 0.5):  # Reduced wait time
                pos = self.get_position()
                self.debug_print(f"  Position: {pos}")
            else:
                self.debug_print("  Failed to move to position 1")
            
            # Move to position 0 (down)
            self.debug_print("  Moving to position 0 (down)...")
            if self.move_and_wait(0, 0.5):  # Reduced wait time
                pos = self.get_position()
                self.debug_print(f"  Position: {pos}")
            else:
                self.debug_print("  Failed to move to position 0")
        
        self.debug_print("Cycle test completed.")

    def close(self):
        """Close the connection - Call this when done"""
        self._disconnect_device()


if __name__ == "__main__":
    """Test the optimized MFF101 class"""
    # Set debug_mode=True to see debug output, False to suppress it
    mff = Thorlabs_MFF101(debug_mode=True)
    
    print("Testing Optimized Thorlabs MFF101 Class")
    print("=" * 50)
    
    try:
        # Test device connection
        if mff.is_connected():
            print("✓ Device connected!")
            info = mff.get_device_info()
            if info:
                print(f"Device info: {info}")
            
            # Test movement
            print("\nTesting movement...")
            mff.move_and_wait(1, 0.5)
            print(f"Position after move to 1: {mff.get_position()}")
            
            mff.move_and_wait(0, 0.5)
            print(f"Position after move to 0: {mff.get_position()}")
            
            # Test toggle functions
            print("\nTesting toggle functions...")
            
            print("1. Testing toggle_position():")
            mff.toggle_position()
            print(f"   Position after toggle_position: {mff.get_position()}")
            
            print("2. Testing toggle():")
            mff.toggle()
            print(f"   Position after toggle: {mff.get_position()}")
            
            print("3. Testing move_to_opposite():")
            mff.move_to_opposite()
            print(f"   Position after move_to_opposite: {mff.get_position()}")
            
            print("4. Testing get_current_position_name():")
            position_name = mff.get_current_position_name()
            print(f"   Current position name: {position_name}")
            
            # Test cycles
            print("\nTesting cycles...")
            mff.cycle_test(2)
            
        else:
            print("❌ Device not found!")
    
    finally:
        # Always close the connection
        mff.close()
    
    print("\nTest completed.")






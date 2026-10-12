#!/usr/bin/env python3
"""
Simple COM port test to verify Thorlabs filter wheel communication
"""

import serial
import serial.tools.list_ports
import time

def list_ports():
    """List all available COM ports"""
    print("Available COM Ports:")
    for port in serial.tools.list_ports.comports():
        print(f"  {port.device}: {port.description}")
    print()

def test_port(port_name, baud_rate=115200):
    """Test communication with a specific port"""
    print(f"\nTesting {port_name} at {baud_rate} baud...")
    
    try:
        # Open serial port
        ser = serial.Serial(
            port=port_name,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2
        )
        
        print(f"[OK] Successfully opened {port_name}")
        print(f"  Settings: {baud_rate}-8-N-1")
        
        # Wait for connection to stabilize
        time.sleep(0.5)
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Test 1: Try MGMSG_HW_REQ_INFO (APT protocol)
        print("\nTest 1: Sending APT HW_REQ_INFO command...")
        apt_cmd = bytes([0x05, 0x00, 0x00, 0x00, 0x50, 0x01])
        ser.write(apt_cmd)
        time.sleep(0.5)
        
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting)
            print(f"[OK] Response received ({len(response)} bytes): {response.hex()}")
        else:
            print("[NO] No response")
        
        # Test 2: Try text-based ID query
        ser.reset_input_buffer()
        print("\nTest 2: Sending *IDN? command...")
        ser.write(b'*IDN?\r')
        time.sleep(0.5)
        
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting)
            print(f"[OK] Response: {response.decode('ascii', errors='ignore')}")
        else:
            print("[NO] No response")
        
        # Test 3: Try position query (APT protocol)
        ser.reset_input_buffer()
        print("\nTest 3: Sending APT GET_POSITION command...")
        apt_pos_cmd = bytes([0x11, 0x04, 0x01, 0x00, 0x50, 0x01])
        ser.write(apt_pos_cmd)
        time.sleep(0.5)
        
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting)
            print(f"[OK] Response received ({len(response)} bytes): {response.hex()}")
        else:
            print("[NO] No response")
        
        # Close port
        ser.close()
        print(f"\n[OK] Port {port_name} closed successfully")
        
        return True
        
    except serial.SerialException as e:
        print(f"[ERROR] {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=== Thorlabs Filter Wheel COM Port Test ===\n")
    
    # List all ports
    list_ports()
    
    # Test COM6
    port = input("Enter COM port to test (default: COM6): ").strip()
    if not port:
        port = "COM6"
    
    test_port(port)
    
    print("\n=== Test Complete ===")


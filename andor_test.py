import time
import win32event
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors
import numpy as np
import matplotlib.pyplot as plt

def main():
    # Initialize SDK
    sdk = atmcd()
    ret = sdk.Initialize("")
    if ret != atmcd_errors.Error_Codes.DRV_SUCCESS:
        print(f"Camera initialization failed (Error: {ret})")
        return

    print("Camera initialized successfully")
    
    while True:
        print("\nAndor Camera Control")
        print("1. Start Cooling")
        print("2. Check Temperature")
        print("3. Take Single Shot")
        print("4. Exit")
        choice = input("Select an option (1-4): ")

        if choice == '1':
            # Start cooling
            target_temp = -60
            ret = sdk.SetTemperature(target_temp)
            if ret != atmcd_errors.Error_Codes.DRV_SUCCESS:
                print(f"Failed to set temperature (Error: {ret})")
                continue

            ret = sdk.CoolerON()
            if ret != atmcd_errors.Error_Codes.DRV_SUCCESS:
                print(f"Failed to turn cooler on (Error: {ret})")
                continue
            
            print(f"Cooling started. Target temperature: {target_temp}°C")

        elif choice == '2':
            # Check temperature
            ret, temp = sdk.GetTemperature()
            status = "Stabilized" if ret == atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED else "Cooling"
            print(f"Temperature: {temp}°C ({status}) [Code: {ret}]")

        elif choice == '3':
            # Take single shot
            try:
                # Set acquisition parameters
                sdk.SetAcquisitionMode(atmcd_codes.Acquisition_Mode.SINGLE_SCAN)
                sdk.SetReadMode(atmcd_codes.Read_Mode.FULL_VERTICAL_BINNING)
                # sdk.SetTriggerMode(atmcd_codes.Trigger_Mode.INTERNAL)
                
                # Get detector size
                ret, xpixels, ypixels = sdk.GetDetector()
                if ret != atmcd_errors.Error_Codes.DRV_SUCCESS:
                    print(f"Failed to get detector size (Error: {ret})")
                    continue

                # Set exposure time (in seconds)
                sdk.SetExposureTime(0.1)

                # Start acquisition
                ret = sdk.PrepareAcquisition()
                print("Function PrepareAcquisition returned {}".format(ret))

                # Perform Acquisition
                ret = sdk.StartAcquisition()
                print("Function StartAcquisition returned {}".format(ret))

                ret = sdk.WaitForAcquisition()
                print("Function WaitForAcquisition returned {}".format(ret))

                # Get the spectrum data
                imageSize = xpixels
                ret, spectrum_data, validfirst, validlast = sdk.GetImages16(1, 1, imageSize)
                print("Function GetImages16 returned {}".format(ret))
                if ret != atmcd_errors.Error_Codes.DRV_SUCCESS:
                    print(f"Failed to acquire image (Error: {ret})")
                    continue

                # Plot the spectrum
                wavelength = np.linspace(400, 800, len(spectrum_data))
                plt.figure()
                plt.plot(wavelength, spectrum_data)
                plt.xlabel('Wavelength (nm)')
                plt.ylabel('Intensity (counts)')
                plt.title('Andor Spectrum')
                plt.grid(True)
                plt.show()

            except Exception as e:
                print(f"Error during acquisition: {str(e)}")

        elif choice == '4':
            # Cleanup and exit
            sdk.CoolerOFF()
            time.sleep(1)  # Wait for cooler to turn off
            sdk.ShutDown()
            print("Camera shut down successfully")
            break

        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()

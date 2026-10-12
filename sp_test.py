import pylablib as pll 
import matplotlib.pyplot as plt
import numpy as np
import time  # 추가
pll.par["devices/dlls/andor_sdk2"] = "C:/Program Files/Andor SOLIS" 
from pylablib.devices import Andor 

# Initialize camera
cam = Andor.AndorSDK2Camera()

# Set default temperature and turn on cooler
try:
    print("Setting default temperature to -60°C...")
    cam.set_temperature(-60)
    cam.set_cooler(True)
    print("Cooler turned ON")
except Exception as e:
    print(f"Error setting default temperature: {str(e)}")

print("\n=== Andor Camera Control ===")
print("Enter 'help' to see available methods")
print("Enter 'q' to quit")

def live_image():
    """Display live images from the camera"""
    try:
        plt.ion()  # Interactive mode on
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Get initial frame to set up display
        cam.start_acquisition()
        cam.wait_for_frame()
        frame = cam.read_oldest_image()
        
        if frame is None:
            print("Failed to get initial frame")
            return
        
        # Check if data is 1D or 2D
        if frame.ndim == 1:
            line, = ax.plot(frame, 'b-')
            ax.set_xlabel('Pixel')
            ax.set_ylabel('Intensity')
            ax.set_title('Live Spectrum')
        else:
            im = ax.imshow(frame, cmap='gray', vmin=frame.min(), vmax=frame.max())
            plt.colorbar(im, label='Intensity')
            ax.set_title('Live Image')
        plt.show()

        print("Live view started. Press any key to stop...")
        
        # Initialize timing variables
        last_time = time.time()
        frame_count = 0
        
        while True:
            if plt.waitforbuttonpress(0.01):  # Check for key press
                break
            
            cam.wait_for_frame()
            frame = cam.read_oldest_image()
            if frame is not None:
                # Update plot based on data dimension
                if frame.ndim == 1:
                    line.set_ydata(frame)
                    ax.relim()
                    ax.autoscale_view()
                else:
                    im.set_data(frame)
                    im.set_clim(vmin=frame.min(), vmax=frame.max())
                fig.canvas.draw()
                fig.canvas.flush_events()
                
                # Calculate and print timing
                current_time = time.time()
                frame_time = current_time - last_time
                last_time = current_time
                frame_count += 1
                frame_time_msec = frame_time * 1000
                fps = 1.0 / frame_time if frame_time > 0 else 0
                print(f"Frame time: {frame_time_msec:.2f} msec, FPS: {fps:.2f}")
                
    except Exception as e:
        print(f"Error during live view: {str(e)}")
    finally:
        cam.stop_acquisition()
        plt.ioff()  # Interactive mode off
        plt.close()
        print("Live view stopped")

while True:
    cmd = input("\nCommand: ")
    
    if cmd.lower() == 'q':
        print("Shutting down...")
        cam.set_cooler(False)
        cam.close()
        break
        
    elif cmd.lower() == 'help':
        methods = [method for method in dir(cam) if not method.startswith('_')]
        print("\nAvailable methods:")
        for method in sorted(methods):
            print(f"- {method}")
        print("- live: Start live image view")
            
    elif cmd.lower() == 'live':
        live_image()
        
    else:
        try:
            func = getattr(cam, cmd, None)
            
            if func is None:
                print(f"Method '{cmd}' not found. Use 'help' to see available methods.")
                continue
                
            if callable(func):
                try:
                    params = input("Enter parameters (comma separated) or press Enter for none: ")
                    
                    args = []
                    kwargs = {}
                    
                    if params.strip():
                        # Split by comma, but not within parentheses
                        param_list = [p.strip() for p in params.split(',')]
                        
                        for param in param_list:
                            if '=' in param:
                                # This is a keyword argument
                                key, value = param.split('=')
                                kwargs[key.strip()] = eval(value.strip())
                            else:
                                # This is a positional argument
                                args.append(eval(param))
                    
                    result = func(*args, **kwargs)
                    
                    # Modify snap command handling
                    if cmd == 'snap' and result is not None:
                        print(result)
                        print(result.shape)
                        plt.figure(figsize=(10, 6))
                        if result.shape == (1, 1024):
                            plt.plot(result, 'b-')
                            plt.xlabel('Pixel')
                            plt.ylabel('Intensity')
                            plt.title('Captured Spectrum')
                        else:
                            plt.imshow(result, cmap='gray')
                            plt.colorbar(label='Intensity')
                            plt.title('Captured Image')
                        plt.show()
                    elif result is not None:
                        print(f"Result: {result}")
                    else:
                        print("Command executed successfully")
                        
                except Exception as e:
                    print(f"Error executing command: {str(e)}")
            else:
                print(f"Value: {func}")
                
        except Exception as e:
            print(f"Error: {str(e)}")

print("Program ended") 

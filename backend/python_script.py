import serial
import time

# Adjust port if needed
arduino = serial.Serial('COM7', 115200, timeout=1)
time.sleep(3)  # wait for Arduino reset

def send_command(cmd, timeout=100):
    arduino.write((cmd + "\n").encode())
    start = time.time()
    while True:
        line = arduino.readline().decode(errors="ignore").strip()
        if line:
            print("Arduino:", line)
            if line.startswith("Done"):
                break
        if time.time() - start > timeout:
            print(f"Timeout: no 'Done' received within {timeout} seconds") # 100 secs
            break


cmd = input()

while (cmd != "stop"):
    send_command(cmd)
    cmd = input()

time.sleep(1)

arduino.close()

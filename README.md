# Project Overview

In this school project made with MicroPython, I collaborated in the design of an automated aquarium. The key features I developed include:
* A water level control system to maintain a consistent water level inside the tank.
* A temperature control system to keep the water temperature within a specified range.
* A web interface that allows users to control and modify the state of various actuators
* The ability to change the color and brightness of an array of neopixels.
* The ability to drain the aquarium when necessary.
* The option to activate a filter for water purification.
  
<img width="752" alt="Captura de pantalla 2024-08-14 a la(s) 9 51 05" src="https://github.com/user-attachments/assets/7dd51c21-afa5-4878-a891-f233f6689c97">

## Tasks Handled by the RP2040
The RP2040 retrieves requests from UART. Depending of what it read it will:
* Turn the neopixels on or off and adjust their color and brightness.
* Activate or deactivate the filter.
* Control the output pump.
* Raise or lower the neopixels.

Additionally, the RP2040 uses a level sensor and a Pt100 sensor to monitor the water level and temperature, respectively. Based on these readings, it controls the input pump, fan, and heater as needed.

The status of certain devices (such as the fan, heater, and pumps) is displayed on the web page, so the RP2040 must send this information via UART when necessary.

## Tasks Handled by the ESP32
The ESP32 hosts the web server and handles data transmission via UART. The data sent consists of commands from the web interface, which directly affect the actuators connected to the RP2040 or request specific information.

The ESP32 also updates the information displayed on the web server whenever there is a change in the system.

## Web interface description
The web interface is divided into two sections:
* *Body*: Contains buttons to turn the respective actuators on or off, along with text boxes for inputting color and brightness settings.
* *Footer*: Displays information such as temperature, water level, and the status of the fan, heater, and pump.

he HTML code includes JavaScript functions that handle these requests.

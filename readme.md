# Heart<i>ex</i>

A python program to read heart rate data using the [pulse sensor](http://pulsesensor.myshopify.com/) via an Arduino microcontroller.

This program calculates heart rate variability parameters and displays these in real-time in a user interface based on [matplotlib](). The data then is saved in an excel spreadsheet.

Also provided is a modified version of the code to run on the Arduino (in the directory "PulseSensorAmped_Arduino").
With the modified code the LED is switched on when you press the button on the Arduino. This way you can keep the Arduino connected all the time and only turn on the LED for measurements.

![screenshot](https://raw.githubusercontent.com/00alexx/heartex/master/screenshot.png

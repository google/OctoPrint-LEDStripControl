# OctoPrint-LED-Strip-Control

OctoPrint Plugin that intercepts M150 GCode commands and controls local GPIOs accordingly.

Implements the M150 command syntax from the latest Marlin.

        M150: Set Status LED Color - Use R-U-B for R-G-B
        M150 R255       ; Turn LED red
        M150 R255 U127  ; Turn LED orange (PWM only)
        M150            ; Turn LED off
        M150 R U B      ; Turn LED white

## Setup

1. Make sure that the OctoPrint user is in the gpio group via the following command.

    	usermod -G gpio pi

1. Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    	https://github.com/google/OctoPrint-LEDStripControl/archive/master.zip

1. Restart OctoPrint

## Configuration

**NOTE: GPIO pins should be specified as phsyical number and not BCM number.**

Configure the GPIO pins via the OctoPrint settings UI.

## Disclaimer

This is **not** an official Google product.

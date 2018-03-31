#
# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# coding=utf-8

from __future__ import absolute_import
import re

import octoprint.plugin
import pigpio
try:
	import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
	# RuntimeError gets thrown when you import RPi.GPIO on a non Raspberry Pi
	GPIO = None

phy_to_bcm = { 0:None, 1:None, 2:None, 3:2, 4:None, 5:3, 6:None, 7:4, 8:14,
			  9:None, 10:15, 11:17, 12:18, 13:27, 14:None, 15:22, 16:23,
			  17:None, 18:24, 19:10, 20:None, 21:9, 22:25, 23:11, 24:8, 25:None,
			  26:7, 27:0, 28:1, 29:5, 30:None, 31:6, 32:12, 33:13, 34:None,
			  35:19, 36:16, 37:26, 38:20, 39:None, 40:21 }

class PiGPIOpin(object):
	def __init__(self, pigpiod, pin, logger):
		self._pigpiod = pigpiod
		self._logger = logger

		# attempt to convert the physical pin to a bcm pin
		# how is this not in a library already?
		if phy_to_bcm.get(pin) is not None:
			self._pin = phy_to_bcm[pin]
		else:
			self._pin = pin
		self._logger.debug(u"PiGPIOpin: coverted pin: %r to %r" % (pin, self._pin))

		self._dutycycle = 0

	def start(self, dutycycle):
		self._dutycycle = dutycycle
		self._logger.debug(u"PiGPIOpin: start() pin: %s" % self._pin)
		if self._pigpiod.connected:
			self._pigpiod.set_PWM_dutycycle(self._pin, dutycycle)

	def stop(self):
		self._logger.debug(u"PiGPIOpin: stop() pin: %s" % self._pin)
		if self._pigpiod.connected:
			self._pigpiod.set_PWM_dutycycle(self._pin, 0)

	def ChangeDutyCycle(self, dutycycle):
		self._logger.debug(u"PiGPIOpin: ChangeDutyCycle() pin: %s" % self._pin)
		self.start(float(dutycycle))

class LEDStripControlPlugin(octoprint.plugin.AssetPlugin,
							octoprint.plugin.SettingsPlugin,
							octoprint.plugin.ShutdownPlugin,
							octoprint.plugin.StartupPlugin,
							octoprint.plugin.TemplatePlugin):

	def __init__(self):
		self._leds = dict(r=None, g=None, b=None, w=None)
		self._pigpiod = None

	def _setup_pin(self, pin):
		self._logger.debug(u"_setup_pin(%s)" % (pin,))
		if pin:
			p = None
			startup = 255.0 if self._settings.get_boolean(['on_startup']) else 0.0

			if self._pigpiod is None:
				self._pigpiod = pigpio.pi()

			if self._settings.get_boolean(['pigpiod']):
				if not self._pigpiod.connected:
					self._logger.error(u"Unable to communicate with PiGPIOd")
				else:
					p = PiGPIOpin(self._pigpiod, pin, self._logger)
			else:
				GPIO.setwarnings(False)
				GPIO.setmode(GPIO.BOARD)
				GPIO.setup(pin, GPIO.OUT)
				GPIO.output(pin, GPIO.HIGH)
				p = GPIO.PWM(pin, 100)
			p.start(float(startup))
			return p

	def _unregister_leds(self):
		self._logger.debug(u"_unregister_leds()")
		for i in ('r', 'g', 'b', 'w'):
			try:
				if self._leds[i]:
					self._leds[i].ChangeDutyCycle(0)
					self._leds[i].stop()
			except KeyError:
				pass

		if not self._settings.get_boolean(['pigpiod']) and GPIO:
			GPIO.cleanup()
		self._leds = dict(r=None, g=None, b=None)

	def _register_leds(self):
		self._logger.debug(u"_register_leds()")
		for i in ('r', 'g', 'b', 'w'):
			pin = self._settings.get_int([i])
			self._logger.debug(u"got pin(%s)" % (pin,))
			self._leds[i] = self._setup_pin(pin)

	def on_after_startup(self):
		self._logger.debug(u"LEDStripControl Startup")
		if GPIO:
			self._logger.debug(u"RPi.GPIO version %s" % (GPIO.VERSION,))

	def on_shutdown(self):
		self._logger.debug(u"LEDStripControl Shutdown")
		self._unregister_leds()
		self._pigpiod.stop()

	def HandleM150(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		if gcode and cmd.startswith("M150"):
			self._logger.debug(u"M150 Detected: %s" % (cmd,))
			# Emulating Marlin 1.1.0's syntax
			# https://github.com/MarlinFirmware/Marlin/blob/RC/Marlin/Marlin_main.cpp#L6133
			dutycycles = {'r':0.0, 'g':0.0, 'b':0.0, 'w':0.0}
			for match in re.finditer(r'([RGUBWrgubw]) *(\d*)', cmd):
				k = match.group(1).lower()
				# Marlin uses RUB instead of RGB
				if k == 'u': k = 'g'
				try:
					v = float(match.group(2))
				except ValueError:
					# more than likely match.group(2) was unspecified
					v = 255.0
				v = v/255.0 * 100.0 # convert RGB to RPi dutycycle
				v = max(min(v, 100.0), 0.0) # clamp the value
				dutycycles[k] = v
				self._logger.debug(u"match 1: %s 2: %s" % (k, v))

			for l in dutycycles.keys():
				if self._leds[l]:
					self._leds[l].ChangeDutyCycle(dutycycles[l])

			return None,

			return None,

	##~~ SettingsPlugin mixin

	def get_settings_version(self):
		return 1

	def get_template_configs(self):
		return [
			dict(type="settings", name="LED Strip Control", custom_bindings=False)
		]

	def get_settings_defaults(self):
		return dict(r=0, g=0, b=0, w=0, pigpiod=False, on_startup=True)

	def on_settings_initialized(self):
		self._logger.debug(u"LEDStripControl on_settings_load()")

		self._register_leds()

	def on_settings_save(self, data):
		self._logger.debug(u"LEDStripControl on_settings_save()")
		self._unregister_leds()
		# cast to proper types before saving
		for k in ('r', 'g', 'b', 'w'):
			if data.get(k): data[k] = max(0, int(data[k]))
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self._register_leds()

	##~~ Softwareupdate hook

	def get_update_information(self):
		return dict(
			ledstripcontrol=dict(
				displayName="LED Strip Control Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="google",
				repo="OctoPrint-LEDStripControl",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/google/OctoPrint-LEDStripControl/archive/{target_version}.zip"
			)
		)

__plugin_name__ = "LED Strip Control"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = LEDStripControlPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.HandleM150
	}


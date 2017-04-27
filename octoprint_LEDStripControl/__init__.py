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
import os.path
import re

import octoprint.plugin
import RPi.GPIO as GPIO

class PiBlasterPin(object):
	def __init__(self, pin):
		self._dev = "/dev/pi-blaster"
		self._pin = pin
		self._dutycycle = 0

	def _write_to_dev(self, cmd):
		if not os.path.exists(self._dev):
			raise Exception("%s does not exist" % self._dev)
		if not os.access(self._dev, os.W_OK):
			raise Exception("%s is not writable" % self._dev)
		with open(self._dev, "w") as pb:
			pb.write(cmd + "\n")

	def start(self, dutycycle):
		self._dutycycle = dutycycle
		# munge the output for pi-blaster
		dc = "%0.1f" % (self._dutycycle / 100.0)
		dc = dc.rstrip("0").rstrip(".")
		self._write_to_dev("%s=%s" % (self._pin, dc))

	def stop(self):
		self._write_to_dev("%s=0" % self._pin)

	def ChangeDutyCycle(self, dutycycle):
		self.start(dutycycle)

class LEDStripControlPlugin(octoprint.plugin.AssetPlugin,
							octoprint.plugin.SettingsPlugin,
							octoprint.plugin.ShutdownPlugin,
							octoprint.plugin.StartupPlugin,
							octoprint.plugin.TemplatePlugin):

	def __init__(self):
		self._leds = dict(r=None, g=None, b=None)

	def _setup_pin(self, pin):
		self._logger.debug(u"_setup_pin(%s)" % (pin,))
		if pin:
			p = None

			if self._settings.get_boolean(['piblaster']):
				p = PiBlasterPin(pin)
			else:
				GPIO.setwarnings(False)
				GPIO.setmode(GPIO.BOARD)
				GPIO.setup(pin, GPIO.OUT)
				GPIO.output(pin, GPIO.HIGH)
				p = GPIO.PWM(pin, 100)
			p.start(100)
			return p

	def _unregister_leds(self):
		self._logger.debug(u"_unregister_leds()")
		for i in ('r', 'g', 'b'):
			if self._leds[i]:
				self._leds[i].ChangeDutyCycle(0)
				self._leds[i].stop()

		if not self._settings.get_boolean(['piblaster']):
			GPIO.cleanup()
		self._leds = dict(r=None, g=None, b=None)

	def _register_leds(self):
		self._logger.debug(u"_register_leds()")
		for i in ('r', 'g', 'b'):
			pin = self._settings.get_int([i])
			self._logger.debug(u"got pin(%s)" % (pin,))
			self._leds[i] = self._setup_pin(pin)

	def on_after_startup(self):
		self._logger.debug(u"LEDStripControl Startup")
		self._logger.debug(u"RPi.GPIO version %s" % (GPIO.VERSION,))

	def on_shutdown(self):
		self._logger.debug(u"LEDStripControl Shutdown")
		self._unregister_leds()

	def HandleM150(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		if gcode and cmd.startswith("M150"):
			self._logger.debug(u"M150 Detected: %s" % (cmd,))
			# Emulating Marlin 1.1.0's syntax
			# https://github.com/MarlinFirmware/Marlin/blob/RC/Marlin/Marlin_main.cpp#L6133
			dutycycles = {'r':0.0, 'g':0.0, 'b':0.0}
			for match in re.finditer(r'([RGUBrgub]) *(\d*)', cmd):
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
				self._leds[l].ChangeDutyCycle(dutycycles[l])

	##~~ SettingsPlugin mixin

	def get_settings_version(self):
		return 1

	def get_template_configs(self):
		return [
			dict(type="settings", name="LED Strip Control", custom_bindings=False)
		]

	def get_settings_defaults(self):
		return dict(r=0, g=0, b=0, piblaster=False)

	def on_settings_initialized(self):
		self._logger.debug(u"LEDStripControl on_settings_load()")
		self._register_leds()

	def on_settings_save(self, data):
		self._logger.debug(u"LEDStripControl on_settings_save()")
		self._unregister_leds()
		# cast to proper types before saving
		for k in ('r', 'g', 'b'):
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


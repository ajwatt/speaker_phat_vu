# Speaker pHAT VU meter for Home Assistant OS

Experimental local add-on for a Raspberry Pi 4 with a Speaker pHAT. Audio must
already work. The add-on reads a PulseAudio output monitor and updates the ten
LEDs over I2C. It does not modify audio routing or install software on the host.
No microphone is needed. Samples are processed in memory and discarded.

## Enable I2C

Keep the working `dtoverlay=hifiberry-dac` setting. In the boot partition's
`config.txt`, add the following under an applicable `[all]` section:

```ini
dtparam=i2c_arm=on
```

Load `i2c-dev` at boot using the documented HAOS CONFIG USB mechanism:

1. On a USB drive labeled `CONFIG`, create `modules/rpi-i2c.conf` containing
   just `i2c-dev` followed by a newline.
2. Connect it to HAOS, run `ha os import`, then reboot the host.
3. From the actual host shell, verify `ls -l /dev/i2c-1`.

The local HA console's `login` command enters the host shell. A normal terminal
add-on has its own device namespace and may not show the host's I2C device.

Reference: https://contributors.home-assistant.io/os/operating-system/raspberry-pi/

## Install

1. Copy the entire `speaker_phat_vu` folder to HA's local add-ons directory,
   commonly `/addons` in a terminal add-on or the `addons` Samba share.
   The resulting path in that share must be `speaker_phat_vu/config.yaml`.
   Do not place it in Home Assistant's `/config` folder.
2. Reload/check for updates in the app/add-on store. Open **Speaker pHAT VU
   Meter** under **Local apps/add-ons** and install it. Supervisor builds the
   container on the Pi; internet access is needed to fetch its base and packages.
3. Start the add-on and inspect its log. The LEDs should briefly chase once.
4. Play audio. Initially the meter monitors the default PulseAudio output.
5. If the pHAT is not the default output, copy its exact source name ending in
   `.monitor` from the log into the `source` option and restart the add-on.
6. Enable **Start on boot** after verifying operation.

Keep protection mode enabled. This add-on requests only `/dev/i2c-1` and HA's
audio connection. It does not need GPIO, full access, host networking, or access
to the Home Assistant API.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| source | `@DEFAULT_MONITOR@` | PulseAudio output monitor; explicit pHAT monitor recommended if multiple outputs exist |
| brightness | 32 | Raw LED PWM from 1 to 255; start low |
| floor_db | -48 | RMS dBFS below which the bar is dark |
| gain_db | 0 | Meter sensitivity; increase if the bar is too low |
| reverse | false | Reverse bar direction |
| startup_test | true | Briefly light each LED on startup |

This is an RMS level display with fast attack and gradual decay, not a calibrated
analog VU meter. It measures digital samples rather than acoustic loudness.
Playback that bypasses HA's PulseAudio service will not appear in its monitor.
If no monitor corresponds to the working output, identify the playback add-on
and its audio configuration before changing anything.

## Troubleshooting

- **Add-on installation/start reports missing device:** enable host I2C and load
  `i2c-dev`; reboot and check `/dev/i2c-1` from the host shell.
- **I2C error / remote I/O error:** check pHAT seating and that no other process
  controls its SN3218 at address `0x54`. Stop other LED services before starting.
- **Startup chase works, but no meter:** inspect available sources in the log
  and select the pHAT's `.monitor`; confirm playback uses PulseAudio.
- **PulseAudio connection errors:** verify the HA audio service is running
  with `ha audio info` and `ha audio logs`. The add-on retries automatically.
- **Wrong direction or sensitivity:** adjust `reverse`, `gain_db`, or `floor_db`.

Stop the add-on to clear the LEDs; uninstall it to remove its software. The I2C
boot setting may remain if other devices use it.

## Validation and references

Not yet tested on a physical Speaker pHAT or built under HAOS. Local checks cover
PCM level calculation, bar thresholds, channel mapping, I2C register writes with
a fake bus, and monitor subprocess behavior. Hardware and Supervisor validation
remain necessary.

- HA add-on configuration: https://contributors.home-assistant.io/apps/reference/configuration/
- HA audio: https://github.com/home-assistant/plugin-audio
- LED wiring: https://github.com/pimoroni/speaker-phat/blob/master/python/speakerphat.py
- SN3218 register protocol: https://github.com/pimoroni/sn3218-python
- PulseAudio capture CLI: https://github.com/pulseaudio/pulseaudio/blob/master/man/pacat.1.xml.in

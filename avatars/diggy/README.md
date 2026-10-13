# Diggy avatar

An animated on-screen face for Diggy, the robot dog. It blinks, perks its ears when listening, looks up when thinking, moves its mouth while speaking, and shows subtitles one sentence at a time. Diggy's eyes, chest light, and the glow behind the face all follow the robot's LED color.

There are two looks. The default is a robot: a metal head with round sensor-lens eyes, a speaker-bar mouth, and an 11-segment chest light that works as a level meter while Diggy speaks, a scanner while it thinks, and a steady glow while it listens. Add `?skin=puppy` for a friendlier cartoon dog. Press `s` to switch between them.

This folder is separate from the SRWToolkit code. SRWToolkit is MIT licensed (see the repo's `LICENSE`); keep that notice if you reuse its code.

## Try it without the robot

Open `diggy_avatar.html` in a browser, tap **Tap to wake Diggy**, then use the buttons at the top left to switch states, pick an LED color, or make Diggy say something. Press `d` to hide those controls and `f` for full screen.

## Connect it to Diggy's dashboard (voice plays on the tablet)

This is set up for the dashboard in `TechPlayzone/PiDog` (`server.py`, Flask on port 5001), where Piper runs on Diggy's Raspberry Pi. The laptop asks Diggy to speak each reply into a WAV file, copies it over, and serves it to the tablet. The tablet plays it, and the mouth follows the real audio.

1. Copy `diggy_avatar.html`, `diggy_avatar_bridge.py`, and `diggy_voice.py` into the same folder as `server.py`.
2. Apply the patch from that folder: `patch -p1 < server_avatar.patch`. It was made against the PiDog repo's `server.py` from June 9, 2026 (commit `bc4aa84`). If your `server.py` has changed since then and the patch doesn't apply, make the same changes by hand; they are small and listed below.
3. Start the dashboard as usual. On the tablet, on the same network, open `http://<laptop-ip>:5001/avatar/` and tap **Tap to wake Diggy** once. Windows may ask to let Python through the firewall the first time.

What the patch changes in `server.py`:

| Where | Change |
|---|---|
| Imports and settings | Loads the bridge and `diggy_voice`, adds `AVATAR_VOICE` |
| `diggy_speak` | With the avatar page open, Diggy makes the voice file, the tablet plays it, and the chest strip shows the speaking light for as long as the audio lasts |
| `diggy_show_thinking`, `diggy_clear_leds` | Tell the avatar to think or go idle |
| `/api/listen` | Tells the avatar Diggy is listening |
| `/api/led` | Passes the LED color to the avatar |
| Flask app | Registers the bridge |

Settings, as environment variables or in `.env`:

- `AVATAR_VOICE=tablet` (default) plays the voice on the tablet only. `robot` plays it on Diggy's speaker only, and `both` plays it in both places.
- `DIGGY_PIPER_MODEL` is the full path to the voice model on Diggy. The default is `/home/<user>/.piper_models/en_US-amy-low.onnx`.
- `DIGGY_PIPER` is the full path to the `piper` program on Diggy, only needed if it isn't found automatically.

If the avatar page isn't open, or making the voice file fails, Diggy speaks on its own speaker as before, so it never goes silent.

## Events

Any dashboard can drive the avatar by calling `publish(...)` from `diggy_avatar_bridge.py`:

| When | Event |
|---|---|
| Microphone is recording | `{"type": "state", "state": "listening"}` |
| Waiting for the LLM | `{"type": "state", "state": "thinking"}` |
| Diggy speaks | `{"type": "speak", "text": reply}` |
| Robot LED color changes | `{"type": "led", "color": "#ff8800"}` |
| Interrupt | `{"type": "stop"}` |
| Subtitles on or off | `{"type": "subtitles", "enabled": false}` |

After a `speak` event finishes, the face returns to idle by itself.

A `speak` event can also carry `"audio_url"` (use `stage_audio("reply.wav")` to get one) so the tablet plays real audio, and `"duration_ms"` so the mouth and subtitles stay in step when there is no audio file.

To test the link without the dashboard, run `python diggy_avatar_bridge.py`, open `http://localhost:5051/avatar/`, and send:

```
curl -X POST -H "Content-Type: application/json" -d '{"text":"Woof! I am Diggy."}' http://localhost:5051/avatar/say
```

## Options

- `?server=http://<ip>:<port>` when the page is opened from somewhere other than the dashboard.
- `?skin=puppy` shows the cartoon dog instead of the robot.
- `?nogate=1` skips the wake button. Don't use it when the voice plays on the tablet, because browsers block sound until someone taps.
- If the browser blocks sound, the page asks for a tap on the screen.
- Reduced-motion settings stop the idle glancing and ear twitches.

The bridge has no login. Run it on a trusted network only.

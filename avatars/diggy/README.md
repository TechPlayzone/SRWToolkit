# Diggy avatar

An animated on-screen face for Diggy, the robot dog. It blinks, perks its ears when listening, looks up when thinking, moves its mouth while speaking, and shows subtitles one sentence at a time. Diggy's eyes, chest light, and the glow behind the face all follow the robot's LED color.

There are two looks. The default is a robot: a metal head with round sensor-lens eyes, a speaker-bar mouth, and an 11-segment chest light that works as a level meter while Diggy speaks, a scanner while it thinks, and a steady glow while it listens. Add `?skin=puppy` for a friendlier cartoon dog. Press `s` to switch between them.

This folder is separate from the SRWToolkit code. SRWToolkit is MIT licensed (see the repo's `LICENSE`); keep that notice if you reuse its code.

## Try it without the robot

Open `index.html` in a browser, tap **Tap to wake Diggy**, then use the buttons at the top left to switch states, pick an LED color, or make Diggy say something. Press `d` to hide those controls and `f` for full screen.

## Connect it to the dashboard

1. Copy `diggy_avatar_bridge.py` next to the dashboard's Flask app.
2. Register it:

   ```python
   from diggy_avatar_bridge import avatar_bp, publish
   app.register_blueprint(avatar_bp)
   ```

3. Open `http://<laptop-ip>:<flask-port>/avatar/` on the tablet, then tap once to wake Diggy.
4. Call `publish(...)` from the dashboard:

   | When | Event |
   |---|---|
   | Microphone is recording | `{"type": "state", "state": "listening"}` |
   | Waiting for the LLM | `{"type": "state", "state": "thinking"}` |
   | Diggy speaks | `{"type": "speak", "text": reply}` |
   | Robot LED color changes | `{"type": "led", "color": "#ff8800"}` |
   | Interrupt | `{"type": "stop"}` |
   | Subtitles on or off | `{"type": "subtitles", "enabled": false}` |

   After a `speak` event finishes, the face returns to idle by itself.

To test the link before touching the dashboard, run `python diggy_avatar_bridge.py`, open `http://localhost:5051/avatar/`, and send:

```
curl -X POST -H "Content-Type: application/json" -d '{"text":"Woof! I am Diggy."}' http://localhost:5051/avatar/say
```

## Where the voice plays

- **Voice plays on the robot's speaker (default).** Send `speak` with just `text`. The mouth follows a timing pattern built from the words. Add `"duration_ms"` if you know how long the audio lasts, so the mouth and subtitles stay in step.
- **Voice plays in the tablet's browser.** Send `speak` with `"audio_url"` (for example a `/tts/latest.wav` route on the dashboard). The mouth then follows the real audio, and subtitles follow its progress. Browsers only allow sound after a tap, which is why the page starts with the wake button.

## Options

- `?server=http://<ip>:<port>` when the page is opened from somewhere other than the dashboard.
- `?skin=puppy` shows the cartoon dog instead of the robot.
- `?nogate=1` skips the wake button, for setups where the robot makes the sound.
- Reduced-motion settings stop the idle glancing and ear twitches.

The bridge has no login. Run it on a trusted network only.

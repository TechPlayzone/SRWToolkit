"""Make Diggy's Piper voice on the robot and bring the WAV back to the laptop.

Diggy's Raspberry Pi already has the Piper voice model, so the laptop asks the Pi to
speak a sentence into a WAV file, then copies that file over SFTP. The dashboard can then
serve the file to the tablet, which plays it and animates the avatar's mouth from the audio.

Settings (all optional, set as environment variables or in .env):
    DIGGY_PIPER         full path to the piper program on Diggy (default: found automatically)
    DIGGY_PIPER_MODEL   full path to the voice model on Diggy
                        (default: /home/<user>/.piper_models/en_US-amy-low.onnx)
"""
import os
import shlex
import tempfile
import wave

import paramiko

REMOTE_WAV = "/tmp/diggy_avatar.wav"

# Runs on Diggy through a login shell, so the same PATH as an ordinary SSH session applies.
# $1 is the voice model and $2 the WAV file to write. The sentence arrives on standard input,
# so nothing the language model writes is ever pasted into a shell command.
_REMOTE_SCRIPT = r"""
PIPER="${DIGGY_PIPER:-$(command -v piper || true)}"
[ -x "$PIPER" ] || PIPER="$HOME/diggy-env/bin/piper"
[ -x "$PIPER" ] || { echo "piper program not found on Diggy" >&2; exit 127; }
"$PIPER" --model "$1" --output_file "$2"
"""


def synthesize_on_diggy(text, host, user, password, model=None, timeout=45):
    """Speak `text` into a WAV file on Diggy and return the path of a copy on this computer."""
    model = model or os.environ.get("DIGGY_PIPER_MODEL") or f"/home/{user}/.piper_models/en_US-amy-low.onnx"
    piper = os.environ.get("DIGGY_PIPER", "")
    script = f"DIGGY_PIPER={shlex.quote(piper)}\n" + _REMOTE_SCRIPT if piper else _REMOTE_SCRIPT
    command = " ".join(["bash", "-lc", shlex.quote(script), "diggy", shlex.quote(model), shlex.quote(REMOTE_WAV)])

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password, timeout=10)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        stdin.write(text.strip() + "\n")
        stdin.flush()
        stdin.channel.shutdown_write()
        if not stdout.channel.status_event.wait(timeout):
            raise TimeoutError(f"Piper on Diggy did not finish within {timeout} seconds")
        status = stdout.channel.recv_exit_status()
        if status != 0:
            detail = stderr.read().decode("utf-8", "ignore").strip()[-300:]
            raise RuntimeError(f"Piper on Diggy exited with status {status}: {detail}")

        fd, local = tempfile.mkstemp(prefix="diggy_say_", suffix=".wav")
        os.close(fd)
        sftp = client.open_sftp()
        try:
            sftp.get(REMOTE_WAV, local)
        finally:
            sftp.close()
        return local
    finally:
        client.close()


def wav_seconds(path):
    """Length of a WAV file in seconds."""
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())

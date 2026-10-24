import io
import struct
import unittest
import wave
from unittest import mock

from lemur_tracker import rewards


def samples_of(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        params = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        frames = w.readframes(w.getnframes())
    return params, struct.unpack(f"<{len(frames) // 2}h", frames)


def zero_crossings(samples, start_s, end_s):
    window = samples[int(start_s * rewards.RATE) : int(end_s * rewards.RATE)]
    return sum(1 for a, b in zip(window, window[1:]) if (a < 0) != (b < 0))


class SynthesisTests(unittest.TestCase):
    def test_sounds_are_valid_mono_wavs(self):
        for render in (lambda: rewards.step_chime(0.5), rewards.unit_done_flourish, rewards.commission_fanfare):
            params, samples = samples_of(render())
            self.assertEqual(params, (1, 2, rewards.RATE))
            self.assertGreater(len(samples), rewards.RATE // 4)
            self.assertGreater(max(abs(s) for s in samples), 1000)

    def test_chime_climbs_one_octave_from_first_step_to_last(self):
        self.assertEqual(rewards.step_pitch(0.0), rewards.STEP_BASE_PITCH)
        self.assertAlmostEqual(rewards.step_pitch(1.0), 2 * rewards.STEP_BASE_PITCH)
        pitches = [rewards.step_pitch(k / 9) for k in range(10)]
        self.assertEqual(pitches, sorted(set(pitches)))  # every step a little higher

    def test_chime_audio_is_at_the_right_pitch(self):
        _, low = samples_of(rewards.step_chime(0.0))
        _, high = samples_of(rewards.step_chime(1.0))
        # Count waves in the main note, after the grace note has faded: an octave doubles them.
        ratio = zero_crossings(high, 0.15, 0.35) / zero_crossings(low, 0.15, 0.35)
        self.assertAlmostEqual(ratio, 2.0, delta=0.1)

    def test_headlines(self):
        self.assertEqual(rewards.headline_for("Prime"), "Primed!")
        self.assertEqual(rewards.headline_for("Glazing"), "Glazing done!")
        self.assertIn(rewards.cheer(), rewards.CHEERS)


class SoundPlayerTests(unittest.TestCase):
    def player(self, command=("aplay", "-q"), enabled=True):
        with mock.patch("lemur_tracker.rewards._find_player", return_value=list(command) if command else None):
            return rewards.SoundPlayer(enabled=enabled)

    @mock.patch("sys.platform", "linux")
    @mock.patch("lemur_tracker.rewards.subprocess.Popen")
    def test_plays_with_platform_command_and_reuses_the_file(self, popen):
        player = self.player()
        player.play_step(0.0)
        player.play_step(0.0)
        self.assertEqual(popen.call_count, 2)
        args = popen.call_args.args[0]
        self.assertEqual(args[:2], ["aplay", "-q"])
        self.assertTrue(args[2].endswith("step523.wav"))
        self.assertEqual(len(player._files), 1)

    @mock.patch("sys.platform", "linux")
    @mock.patch("lemur_tracker.rewards.subprocess.Popen")
    def test_disabled_player_is_silent(self, popen):
        self.player(enabled=False).play_commission_done()
        popen.assert_not_called()

    @mock.patch("sys.platform", "linux")
    @mock.patch("lemur_tracker.rewards.subprocess.Popen")
    def test_no_audio_is_not_an_error(self, popen):
        self.player(command=None).play_unit_done()
        popen.assert_not_called()
        popen.side_effect = OSError("no such device")
        self.player().play_unit_done()

    def test_finds_a_linux_player(self):
        with mock.patch("sys.platform", "linux"), mock.patch(
            "lemur_tracker.rewards.shutil.which", side_effect=lambda name: name == "pw-play"
        ):
            self.assertEqual(rewards._find_player(), ["pw-play"])


if __name__ == "__main__":
    unittest.main()

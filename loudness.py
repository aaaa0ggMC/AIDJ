"""
Audio loudness analysis using soundfile + numpy + pyloudnorm.
Supports two strategies:
  - linear: RMS-based (fast, sample-amplitude only)
  - lufs:   ITU-R BS.1770-4 integrated loudness (K-weighted, human-ear model)
"""
import threading
import soundfile as sf
import numpy as np
import pyloudnorm as pyln

# Cached meter instances keyed by sample rate (creation has overhead)
_meters = {}
_meters_lock = threading.Lock()


def _get_meter(sr):
    with _meters_lock:
        if sr not in _meters:
            _meters[sr] = pyln.Meter(sr)
        return _meters[sr]


def analyze_loudness(filepath):
    """
    Analyze entire audio file.
    Returns {
        "peak_db": float,       # dBFS, per-channel max
        "rms_db": float,        # dBFS, per-channel max
        "integrated_lufs": float,  # ITU-R BS.1770 integrated loudness
    } or None on failure.
    """
    try:
        data, sr = sf.read(filepath, always_2d=True)

        if data.ndim < 2 or data.shape[1] == 0:
            return None

        # -- Peak & RMS: per-channel max --
        ch_peaks = []
        ch_rms = []
        for ch in range(data.shape[1]):
            channel = data[:, ch]
            if len(channel) == 0:
                continue
            ch_peaks.append(float(np.max(np.abs(channel))))
            ch_rms.append(float(np.sqrt(np.mean(channel ** 2))))

        if not ch_peaks:
            return None

        peak = max(ch_peaks)
        rms = max(ch_rms)
        peak_db = 20.0 * np.log10(max(peak, 1e-10))
        rms_db = 20.0 * np.log10(max(rms, 1e-10))

        # -- ITU-R BS.1770 integrated loudness (LUFS) --
        try:
            meter = _get_meter(sr)
            integrated_lufs = meter.integrated_loudness(data)
        except Exception:
            integrated_lufs = None

        return {
            "peak_db": peak_db,
            "rms_db": rms_db,
            "integrated_lufs": integrated_lufs,
        }
    except Exception:
        return None


def loudness_key(info, method):
    """Extract the loudness value to use for comparison, based on strategy."""
    if info is None:
        return None
    if method == "lufs":
        lufs = info.get("integrated_lufs")
        if lufs is not None and not np.isinf(lufs):
            return lufs
        # Fallback to RMS if LUFS failed
    return info.get("rms_db")


def compute_volume(anchor_val, song_val, base_volume=0.5, curve=3.0):
    """
    Compute target MPRIS volume to make song sound as loud as anchor.

    ABSOLUTE from fixed anchor — zero drift.

    Step 1 — linear gain:
      linear_gain = 10^((anchor - song) / 20)
      linear_target = base_vol * linear_gain

    Step 2 — inverse-curve compensation (player warps MPRIS volume):
      Most players (mpv, VLC) apply actual_gain = mpris_vol^curve (cubic by default).
      To cancel this: mpris_target = linear_target^(1/curve)

    curve=1.0 → linear passthrough (strict MPRIS spec players)
    curve=3.0 → mpv/VLC default cubic compensation

    Returns clamped value in [0.05, 1.0].
    """
    if anchor_val is None or song_val is None:
        return base_volume
    db_diff = anchor_val - song_val
    gain = 10.0 ** (db_diff / 20.0)
    linear_target = base_volume * gain
    # Inverse-compensate the player's volume curve
    compensated = linear_target ** (1.0 / max(curve, 0.1))
    return max(0.05, min(1.0, compensated))


class LoudnessCache:
    """Thread-safe cache with background pre-analysis."""

    def __init__(self, method="lufs", curve=3.0):
        self._cache = {}
        self._lock = threading.Lock()
        self._anchor_val = None
        self._base_volume = 0.5
        self.method = method   # "linear" or "lufs"
        self.curve = curve     # volume curve exponent (1.0=linear, 3.0=mpv/VLC default)

    def get(self, filepath):
        """Get or compute loudness (blocking, thread-safe)."""
        with self._lock:
            if filepath in self._cache:
                return self._cache[filepath]
        result = analyze_loudness(filepath)
        with self._lock:
            if filepath not in self._cache:
                self._cache[filepath] = result
            return self._cache[filepath]

    def pre_analyze(self, filepath):
        """Kick off background analysis. No-op if already cached."""
        with self._lock:
            if filepath in self._cache:
                return
        threading.Thread(target=self.get, args=(filepath,), daemon=True).start()

    def set_anchor(self, filepath, base_volume=0.5):
        """Set anchor reference from a file's loudness. Returns target volume."""
        info = self.get(filepath)
        if info is None:
            return base_volume
        val = loudness_key(info, self.method)
        if val is not None:
            self._anchor_val = val
            self._base_volume = base_volume
        return base_volume

    def set_anchor_value(self, anchor_val, base_volume=0.5):
        """Set anchor reference from an explicit loudness value (LUFS or RMS dB)."""
        self._anchor_val = anchor_val
        self._base_volume = base_volume

    @property
    def anchor_val(self):
        return self._anchor_val

    @property
    def base_volume(self):
        return self._base_volume

    def target_volume(self, filepath):
        """Compute absolute target volume relative to the anchor."""
        if self._anchor_val is None:
            return self._base_volume
        info = self.get(filepath)
        song_val = loudness_key(info, self.method)
        if song_val is None:
            return self._base_volume
        return compute_volume(self._anchor_val, song_val, self._base_volume, self.curve)

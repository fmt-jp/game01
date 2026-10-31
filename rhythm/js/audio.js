// Every sound is built here rather than loaded, so the game carries no audio
// files, and everything is scheduled against the audio clock -- the only clock
// that stays in step with what you actually hear.
const RhythmAudio = (() => {
  const LOOKAHEAD = 0.25;      // seconds of music queued in advance
  // The clock moves in blocks of 128 samples, about 3ms at 44.1kHz, so a
  // sound asked for any sooner than that may already be in the past by the
  // time it is set up -- and anything in the past plays at once, as a click.
  const CUSHION = 0.015;
  const TICK = 25;             // milliseconds between scheduling passes

  function create() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();

    const master = ctx.createGain();
    master.gain.value = 0.9;
    master.connect(ctx.destination);

    const musicBus = ctx.createGain();
    musicBus.gain.value = 0.55;
    musicBus.connect(master);

    // one second of noise, reused for every drum
    const noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const channel = noise.getChannelData(0);
    for (let i = 0; i < channel.length; i++) channel[i] = Math.random() * 2 - 1;

    let songStart = 0;
    let song = null;
    let nextBacking = 0;
    let timer = null;
    const scheduled = [];        // what was queued and when, for the checks

    function note(at, type, wanted) {
      scheduled.push({
        at: +at.toFixed(4), type,
        late: at < ctx.currentTime,
        pushed: wanted !== undefined && at > wanted + 1e-6,
      });
    }

    function envelope(at, peak, attack, decay) {
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(peak, at + attack);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
      return gain;
    }

    function drum(type, at) {
      if (type === "hat" || type === "snare") {
        const src = ctx.createBufferSource();
        src.buffer = noise;
        const filter = ctx.createBiquadFilter();
        filter.type = "highpass";
        filter.frequency.value = type === "hat" ? 7800 : 1600;
        const gain = envelope(at, type === "hat" ? 0.12 : 0.3, 0.002,
                              type === "hat" ? 0.035 : 0.11);
        src.connect(filter).connect(gain).connect(musicBus);
        src.start(at);
        src.stop(at + 0.2);
        return;
      }
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(140, at);
      osc.frequency.exponentialRampToValueAtTime(46, at + 0.11);
      const gain = envelope(at, 0.75, 0.004, 0.14);
      osc.connect(gain).connect(musicBus);
      osc.start(at);
      osc.stop(at + 0.3);
    }

    function bass(midi, at) {
      const osc = ctx.createOscillator();
      osc.type = "triangle";
      osc.frequency.value = Song.midiToFreq(midi);
      const gain = envelope(at, 0.4, 0.01, 0.34);
      osc.connect(gain).connect(musicBus);
      osc.start(at);
      osc.stop(at + 0.5);
    }

    // The melody only sounds when the player hits it, so a run of good taps is
    // the tune and a miss is a hole in it.
    function pluck(midi, at, strength = 1) {
      const freq = Song.midiToFreq(midi);
      for (const [type, level, decay] of [["triangle", 0.42, 0.34], ["sine", 0.26, 0.5]]) {
        const osc = ctx.createOscillator();
        osc.type = type;
        osc.frequency.value = freq;
        const gain = envelope(at, level * strength, 0.006, decay);
        osc.connect(gain).connect(master);
        osc.start(at);
        osc.stop(at + decay + 0.1);
      }
      note(at, "melody");
    }

    function thud(at) {
      const src = ctx.createBufferSource();
      src.buffer = noise;
      const filter = ctx.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.value = 320;
      const gain = envelope(at, 0.22, 0.004, 0.1);
      src.connect(filter).connect(gain).connect(master);
      src.start(at);
      src.stop(at + 0.2);
    }

    function pump() {
      if (!song) return;
      const horizon = ctx.currentTime - songStart + LOOKAHEAD;
      while (nextBacking < song.backing.length && song.backing[nextBacking].time < horizon) {
        const hit = song.backing[nextBacking++];
        const wanted = songStart + hit.time;
        // If the page stalled and its moment has gone, play it a touch late
        // rather than instantly: a late drum is a wobble, an instant one is a
        // click on top of whatever else is sounding.
        const at = Math.max(wanted, ctx.currentTime + CUSHION);
        if (hit.type === "bass") bass(hit.midi, at);
        else drum(hit.type, at);
        note(at, hit.type, wanted);
      }
    }

    return {
      ctx,
      scheduled,
      now: () => ctx.currentTime,
      state: () => ctx.state,
      latency: () => ctx.outputLatency || ctx.baseLatency || 0,
      async unlock() {
        if (ctx.state !== "running") {
          try { await ctx.resume(); } catch (e) {}
        }
        return ctx.state;
      },
      start(nextSong, leadIn = 1.6) {
        song = nextSong;
        nextBacking = 0;
        scheduled.length = 0;
        songStart = ctx.currentTime + leadIn;
        if (timer) clearInterval(timer);
        timer = setInterval(pump, TICK);
        pump();
        return songStart;
      },
      stop() {
        if (timer) clearInterval(timer);
        timer = null;
        song = null;
      },
      songStart: () => songStart,
      position: () => ctx.currentTime - songStart,
      hit: (midi, strength) => pluck(midi, ctx.currentTime + CUSHION, strength),
      miss: () => thud(ctx.currentTime + CUSHION),
    };
  }

  return { create, LOOKAHEAD, TICK };
})();

if (typeof window !== "undefined") window.RhythmAudio = RhythmAudio;

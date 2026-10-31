// Writes a short piece of music and the chart you play it with. No audio here:
// this is only numbers, so it can be generated and checked without a speaker.
const Song = (() => {
  const LANES = 3;
  const STEPS_PER_BAR = 16;          // sixteenth notes
  const PENTATONIC = [0, 3, 5, 7, 10];

  // Four-chord loops that stay out of trouble in a minor key, as semitone
  // offsets from the root.
  const PROGRESSIONS = [
    [0, 8, 3, 10],
    [0, 10, 8, 7],
    [0, 3, 10, 8],
    [0, 5, 8, 7],
  ];

  // Onsets within a bar. The later ones are busier, and a level only draws
  // from as far down this list as it has earned.
  const RHYTHMS = [
    [0, 4, 8, 12],
    [0, 4, 8, 12, 14],
    [0, 4, 6, 8, 12],
    [0, 2, 4, 8, 12],
    [0, 3, 6, 8, 12],
    [0, 2, 4, 8, 10, 12],
    [0, 4, 6, 8, 10, 12, 14],
    [0, 2, 4, 6, 8, 12, 14],
    [0, 2, 4, 6, 8, 10, 12, 14],
  ];

  function levelConfig(level) {
    const bpm = Math.min(152, 92 + (level - 1) * 5);
    return {
      bpm,
      // more bars as the tempo rises, so a song stays about forty seconds
      bars: Math.round(16 * (bpm / 92)),
      // how far down RHYTHMS this level may reach
      busiest: Math.min(RHYTHMS.length, 3 + Math.floor((level - 1) * 0.9)),
      restChance: Math.max(0.08, 0.34 - (level - 1) * 0.03),
    };
  }

  const pick = (list) => list[Math.floor(Math.random() * list.length)];

  // Scale degree -> midi note, walking up through octaves.
  function degreeToMidi(root, degree) {
    const octave = Math.floor(degree / PENTATONIC.length);
    const step = ((degree % PENTATONIC.length) + PENTATONIC.length) % PENTATONIC.length;
    return root + octave * 12 + PENTATONIC[step];
  }

  function compose(level) {
    const config = levelConfig(level);
    const root = 57 + Math.floor(Math.random() * 5);      // A3 upwards
    const progression = pick(PROGRESSIONS);
    const secPerBeat = 60 / config.bpm;
    const secPerStep = secPerBeat / 4;
    const notes = [];
    const backing = [];

    let degree = 3 + Math.floor(Math.random() * 3);

    for (let bar = 0; bar < config.bars; bar++) {
      const barStart = bar * STEPS_PER_BAR;
      const chord = progression[bar % progression.length];

      // drums and bass hold the pulse whether or not the player hits anything
      backing.push({ step: barStart, type: "kick" });
      backing.push({ step: barStart + 8, type: "kick" });
      backing.push({ step: barStart + 4, type: "snare" });
      backing.push({ step: barStart + 12, type: "snare" });
      for (let s = 0; s < STEPS_PER_BAR; s += 2) {
        backing.push({ step: barStart + s, type: "hat" });
      }
      backing.push({ step: barStart, type: "bass", midi: root + chord - 12 });
      backing.push({ step: barStart + 8, type: "bass", midi: root + chord - 12 });

      // the melody, which is also the chart
      const rhythm = RHYTHMS[Math.floor(Math.random() * config.busiest)];
      for (const onset of rhythm) {
        if (Math.random() < config.restChance) continue;
        // A plain random walk piles up against whichever end it drifts to, and
        // then every note lands in the same lane. Pull it back to the middle.
        const centre = PENTATONIC.length;
        const drift = Math.floor(Math.random() * 5) - 2;
        const pull = degree > centre ? -1 : degree < centre ? 1 : 0;
        degree += drift + (Math.random() < 0.5 ? pull : 0);
        degree = Math.max(0, Math.min(PENTATONIC.length * 2 + 1, degree));
        const midi = degreeToMidi(root + chord, degree);
        const span = PENTATONIC.length * 2 + 2;
        const lane = Math.min(LANES - 1, Math.floor((degree / span) * LANES));
        notes.push({ step: barStart + onset, time: (barStart + onset) * secPerStep, midi, lane });
      }
    }

    notes.sort((a, b) => a.time - b.time);
    // Two taps in one lane too close together cannot be played; nudge the
    // second one sideways rather than dropping it, so the melody survives.
    const MIN_SAME_LANE = 0.16;
    const lastInLane = new Array(LANES).fill(-Infinity);
    for (const note of notes) {
      if (note.time - lastInLane[note.lane] < MIN_SAME_LANE) {
        const free = [0, 1, 2]
          .filter((l) => note.time - lastInLane[l] >= MIN_SAME_LANE)
          .sort((a, b) => Math.abs(a - note.lane) - Math.abs(b - note.lane));
        if (free.length) note.lane = free[0];
      }
      lastInLane[note.lane] = note.time;
    }

    for (const hit of backing) hit.time = hit.step * secPerStep;
    // The scheduler walks this list in order and stops at the first event that
    // is still in the future, so it has to be in time order or everything
    // after the first late entry is never played.
    backing.sort((a, b) => a.time - b.time);
    const length = config.bars * STEPS_PER_BAR * secPerStep;

    return { level, bpm: config.bpm, bars: config.bars, root, progression,
             secPerStep, notes, backing, length, lanes: LANES };
  }

  // A song where one lane barely appears is tiring to play with one thumb, and
  // a song with nothing in it is not a song. Compose until one is neither.
  function usable(song) {
    if (song.notes.length < song.length * 0.8) return false;
    const perLane = new Array(LANES).fill(0);
    for (const note of song.notes) perLane[note.lane]++;
    return Math.min(...perLane) >= song.notes.length * 0.18;
  }

  function generate(level) {
    let last = null;
    for (let attempt = 0; attempt < 40; attempt++) {
      last = compose(level);
      if (usable(last)) return last;
    }
    return last;
  }

  function midiToFreq(midi) {
    return 440 * Math.pow(2, (midi - 69) / 12);
  }

  return { generate, compose, usable, levelConfig, midiToFreq, degreeToMidi,
           LANES, STEPS_PER_BAR, PENTATONIC, RHYTHMS, PROGRESSIONS };
})();

if (typeof window !== "undefined") window.Song = Song;

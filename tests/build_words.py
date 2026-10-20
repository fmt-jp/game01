"""Build words/js/dict.js, the word list for ことばの輪.

IPADIC supplies readings for a third of a million entries, but its own cost is
a poor popularity signal — it ranks アンチモニー alongside 学校 — so every
reading is scored by how often its written form actually appears in wordfreq's
Japanese corpus, and the rare ones are dropped. Long vowels are left out: a ー
on the letter wheel reads as a stray mark rather than a letter, and the words
needing one are all loanwords that would be unreachable anyway.

Needs two packages that are not required to run the game or its checks:

    pip install janome wordfreq

Run it from the repository root; it rewrites words/js/dict.js in place.
"""
import gzip
import pathlib
import unicodedata

import msgpack
from janome import sysdic

MAX_BUCKET = 560          # lower is more frequent; chosen by reading samples
MIN_KANA, MAX_KANA = 3, 6
KATA = "".join(chr(c) for c in range(0x30A1, 0x30F7))
HIRA = "".join(chr(c) for c in range(0x3041, 0x3097))
K2H = str.maketrans(KATA, HIRA)
ALLOWED = set(HIRA)
KEEP_POS = {("名詞", "一般"), ("名詞", "サ変接続"), ("動詞", "自立"),
            ("形容詞", "自立"), ("副詞", "一般")}

# Fine in a dictionary, out of place on a word wheel.
BLOCK_READING = {
    "ちちくび", "ちくび", "にゅうぼう", "せいこう", "ふりん", "ばいしゅん",
    "きょにゅう", "せっくす", "ぽるの", "えっち", "ちつ", "こうもん", "せいえき",
    "せいよく", "せいへき", "いばり", "ゆばり", "どうせいあい", "じさつ",
    "さつじん", "しけい", "れいぷ", "かくせいざい", "たいま", "きちがい",
    "はくち", "めくら", "つんぼ", "びっこ",
}
BLOCK_SURFACE_CHARS = set("姦屍癌癲穢娼淫")


def load_frequency():
    """token -> bucket index, lower meaning more frequent."""
    data_dir = pathlib.Path(msgpack.__file__).parent.parent / "wordfreq" / "data"
    with gzip.open(data_dir / "large_ja.msgpack.gz", "rb") as f:
        data = msgpack.load(f, raw=False)
    freq = {}
    for i, bucket in enumerate(data[1:]):
        for token in bucket:
            freq.setdefault(token, i)
    return freq


def build():
    freq = load_frequency()
    best = {}
    for surface, _l, _r, _c, pos, _it, infl, _b, reading, _p in sysdic.entries().values():
        part = pos.split(",")
        if (part[0], part[1]) not in KEEP_POS:
            continue
        if part[0] in ("動詞", "形容詞") and infl != "基本形":
            continue
        kana = reading.translate(K2H)
        if not (MIN_KANA <= len(kana) <= MAX_KANA):
            continue
        if any(ch not in ALLOWED for ch in kana):
            continue
        if kana in BLOCK_READING or BLOCK_SURFACE_CHARS & set(surface):
            continue
        bucket = freq.get(unicodedata.normalize("NFKC", surface))
        if bucket is None or bucket > MAX_BUCKET:
            continue
        if kana not in best or bucket < best[kana][0]:
            best[kana] = (bucket, surface)
    return best


TEMPLATE = '''// Readings from IPADIC, kept only where the written form is common in real
// Japanese text, so the wheel never asks for アンチモニー. No long vowels: a ー
// on the wheel reads as a stray mark rather than a letter.
// Built by tests/build_words.py; edit that, not this.
const WordDict = (() => {{
  const RAW = {{
{body}
  }};

  const byLength = {{}};
  const all = new Set();
  for (const [len, blob] of Object.entries(RAW)) {{
    const words = blob.split(" ");
    byLength[Number(len)] = words;
    for (const w of words) all.add(w);
  }}

  const lengths = Object.keys(byLength).map(Number).sort((a, b) => a - b);

  function has(word) {{ return all.has(word); }}

  // Every word spellable from `letters`, treated as a multiset: a kana may be
  // used only as many times as the wheel holds it.
  function formableFrom(letters, maxLength) {{
    const pool = {{}};
    for (const ch of letters) pool[ch] = (pool[ch] || 0) + 1;
    const out = [];
    for (const len of lengths) {{
      if (len > maxLength) break;
      for (const word of byLength[len]) {{
        const need = {{}};
        let ok = true;
        for (const ch of word) {{
          need[ch] = (need[ch] || 0) + 1;
          if (need[ch] > (pool[ch] || 0)) {{ ok = false; break; }}
        }}
        if (ok) out.push(word);
      }}
    }}
    return out;
  }}

  return {{ byLength, lengths, all, has, formableFrom, size: all.size }};
}})();

if (typeof window !== "undefined") window.WordDict = WordDict;
'''


def main():
    best = build()
    by_len = {}
    for kana in sorted(best):
        by_len.setdefault(len(kana), []).append(kana)
    body = "\n".join(f'    {n}: "{" ".join(by_len[n])}",' for n in sorted(by_len))
    out = pathlib.Path(__file__).resolve().parent.parent / "words" / "js" / "dict.js"
    out.write_text(TEMPLATE.format(body=body), encoding="utf-8")
    print(f"wrote {out} — {len(best)} words, {out.stat().st_size / 1024:.0f} KB")
    for n in sorted(by_len):
        print(f"  {n} kana: {len(by_len[n])}")


if __name__ == "__main__":
    main()

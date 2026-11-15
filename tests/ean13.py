"""Writing a barcode, from the specification rather than from the game.

barcode/js/scanner.js reads these codes; this writes them. The two were
written from the same published tables and nothing else, so a round trip
through a picture is a real test of the reader.
"""

LEFT_ODD = ["0001101", "0011001", "0010011", "0111101", "0100011",
            "0110001", "0101111", "0111011", "0110111", "0001011"]
LEFT_EVEN = ["0100111", "0110011", "0011011", "0100001", "0011101",
             "0111001", "0000101", "0010001", "0001001", "0010111"]
RIGHT = ["1110010", "1100110", "1101100", "1000010", "1011100",
         "1001110", "1010000", "1000100", "1001000", "1110100"]
PARITY = ["000000", "001011", "001101", "001110", "010011",
          "011001", "011100", "010101", "010110", "011010"]


def check_digit(digits):
    """The last digit, which makes the weighted sum come out even."""
    total = 0
    for i, d in enumerate(digits):
        from_right = len(digits) - 1 - i
        total += d * (3 if from_right % 2 == 0 else 1)
    return (10 - total % 10) % 10


def encode(code):
    """A string of 0s and 1s, one per module; 1 is a dark bar."""
    digits = [int(c) for c in code]
    if len(digits) == 13:
        if check_digit(digits[:12]) != digits[12]:
            raise ValueError(f"{code} does not check out")
        parity = PARITY[digits[0]]
        out = "101"
        for n, d in enumerate(digits[1:7]):
            out += LEFT_EVEN[d] if parity[n] == "1" else LEFT_ODD[d]
        out += "01010"
        for d in digits[7:]:
            out += RIGHT[d]
        return out + "101"
    if len(digits) == 8:
        if check_digit(digits[:7]) != digits[7]:
            raise ValueError(f"{code} does not check out")
        out = "101"
        for d in digits[:4]:
            out += LEFT_ODD[d]
        out += "01010"
        for d in digits[4:]:
            out += RIGHT[d]
        return out + "101"
    raise ValueError("only 13 and 8 digit codes")


def with_check(prefix):
    """Finish a code off with the digit that makes it valid."""
    digits = [int(c) for c in prefix]
    return prefix + str(check_digit(digits))


def row(code, unit=3, quiet=10, dark=20, light=235):
    """One line of greyscale pixels across the code."""
    modules = encode(code)
    out = [light] * (quiet * unit)
    for m in modules:
        out += [dark if m == "1" else light] * unit
    out += [light] * (quiet * unit)
    return out

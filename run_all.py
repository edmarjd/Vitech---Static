"""
run_all.py — Executa encoder/decoder em todos os inputs e planos de bits.
Uso:
    python3 run_all.py --recalc-window 1000
"""

import os
import time
import argparse
from collections import deque

from context_model import ContextModel, NUM_CONTEXTS_1D


# ---------------------------------------------------------------------------
# rANS primitivos
# ---------------------------------------------------------------------------

def _C_rANS(s, state, counts):
    M  = counts[0] + counts[1]
    cs = sum(counts[:s])
    fs = counts[s]
    return (state // fs) * M + cs + (state % fs)


def _encode_symbol(state, s, counts, bitstream):
    fs = counts[s]
    while state >= 2 * fs:
        bitstream.append(state & 1)
        state >>= 1
    return _C_rANS(s, state, counts)


def _D_rANS(state, counts):
    M    = counts[0] + counts[1]
    slot = state % M
    s    = 1 if slot >= counts[0] else 0
    cs   = [0, counts[0]]
    prev = (state // M) * counts[s] + slot - cs[s]
    return s, prev


# ---------------------------------------------------------------------------
# Leitura de símbolos
# ---------------------------------------------------------------------------

def load_symbols(path):
    with open(path, "r") as f:
        content = f.read().replace(",", " ").replace("\n", " ").replace("\r", "")
    tokens = content.split()
    if all(len(t) == 1 for t in tokens if t):
        return [int(x) for x in tokens if x in ("0", "1")]
    return [int(c) for c in content if c in ("0", "1")]


# ---------------------------------------------------------------------------
# Pipeline completo para um arquivo (contexto 1D lookahead)
# ---------------------------------------------------------------------------

def run_one(path, recalc_window):
    symbols = load_symbols(path)
    n = len(symbols)
    n_ctx = NUM_CONTEXTS_1D
    rw = recalc_window
    n_blocks = (n + rw - 1) // rw

    def get_ctx(i):
        """Contexto 1D lookahead: ctx do símbolo i = symbols[i+1]."""
        return symbols[i + 1] if i + 1 < n else 0

    # Pré-varredura por bloco (contexto 1D)
    model_enc = ContextModel(mode="static", num_contexts=n_ctx, recalc_window=rw)
    block_freqs = []
    for b in range(n_blocks):
        counts = [[1, 1] for _ in range(n_ctx)]
        start = b * rw
        end   = min(start + rw, n)
        for i in range(start, end):
            ctx = get_ctx(i)
            counts[ctx][symbols[i]] += 1
        block_freqs.append(model_enc._normalize(counts))
    model_enc.set_block_freqs(block_freqs)

    # -----------------------------------------------------------------------
    # ENCODE (ordem direta 0 → n-1)
    # -----------------------------------------------------------------------
    ctx0    = get_ctx(0)
    counts0 = model_enc.get_counts(ctx0, 0)
    state   = counts0[0] + counts0[1]
    bitstream = []

    t0 = time.time()
    for i in range(n):
        ctx = get_ctx(i)
        blk = i // rw if rw > 0 else None
        c   = model_enc.get_counts(ctx, blk)
        state = _encode_symbol(state, symbols[i], c, bitstream)
    t_enc = time.time() - t0

    bitstream_str = "".join(map(str, bitstream))
    final_state   = state
    hdr_hex       = model_enc.serialize_static_headers()

    # -----------------------------------------------------------------------
    # DECODE (ordem inversa n-1 → 0, contexto 1D: last_decoded)
    # -----------------------------------------------------------------------
    model_dec = ContextModel(mode="static", num_contexts=n_ctx, recalc_window=rw)
    model_dec.load_static_headers(hdr_hex)

    bits_q       = deque(map(int, bitstream_str[::-1]))
    decoded      = [0] * n
    state        = final_state
    last_decoded = 0

    t0 = time.time()
    for i in range(n - 1, -1, -1):
        ctx = last_decoded
        blk = i // rw if rw > 0 else None
        c   = model_dec.get_counts(ctx, blk)
        s, prev = _D_rANS(state, c)
        M = c[0] + c[1]
        while prev < M and bits_q:
            prev = (prev << 1) | bits_q.popleft()
        state        = prev
        decoded[i]   = s
        last_decoded = s
    t_dec = time.time() - t0

    ok = (decoded == symbols)

    # Métricas
    bits_bs    = len(bitstream_str)
    bits_state = final_state.bit_length() if final_state > 0 else 1
    bits_hdr   = model_enc.header_overhead_bits()
    bits_pad   = model_enc.padding_bits()
    bits_total = bits_bs + bits_state + bits_hdr + bits_pad
    taxa = (1.0 - bits_total / n) * 100 if n > 0 else 0.0

    return {
        "n":          n,
        "n_blocks":   n_blocks,
        "bits_bs":    bits_bs,
        "bits_state": bits_state,
        "bits_hdr":   bits_hdr,
        "bits_pad":   bits_pad,
        "bits_total": bits_total,
        "taxa":       taxa,
        "decode_ok":  ok,
        "t_enc":      t_enc,
        "t_dec":      t_dec,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Executa encoder/decoder em todos os inputs e planos de bits")
    parser.add_argument("--recalc-window", type=int, default=1000,
                        help="Tamanho do bloco para recalibração (padrão: 1000)")
    args = parser.parse_args()
    rw = args.recalc_window

    W = 130
    print("=" * W)
    print(f"  RUN ALL  |  contexto=1D lookahead  |  recalc_window = {rw}")
    print("=" * W)

    header_row = (
        f"{'BLOCO':>8} | {'ARQUIVO':<12} | {'ORIGINAL':>10} | {'BLOCOS':>6} | "
        f"{'OVERHEAD':>10} | {'PADDING':>8} | {'ESTADO':>8} | {'BITSTREAM':>10} | "
        f"{'COMPRIMIDO':>11} | {'TAXA':>8} | {'T_ENC':>8} | {'T_DEC':>8} | OK"
    )

    def print_row(label, r):
        ok = "✓" if r["decode_ok"] else "✗"
        print(
            f"{rw:>8} | {label:<12} | {r['n']:>10} | {r['n_blocks']:>6} | "
            f"{r['bits_hdr']:>10} | {r['bits_pad']:>8} | {r['bits_state']:>8} | "
            f"{r['bits_bs']:>10} | {r['bits_total']:>11} | "
            f"{r['taxa']:>7.2f}% | {r['t_enc']:>7.4f}s | {r['t_dec']:>7.4f}s | {ok}"
        )

    def print_global(g_n, g_bs, g_state, g_hdr, g_pad, g_total):
        if g_n > 0:
            g_taxa = (1.0 - g_total / g_n) * 100
            print("-" * W)
            print(
                f"{'':>8} | {'GLOBAL':<12} | {g_n:>10} | {'':>6} | "
                f"{g_hdr:>10} | {g_pad:>8} | {g_state:>8} | {g_bs:>10} | "
                f"{g_total:>11} | {g_taxa:>7.2f}% | {'':>8} | {'':>8} |"
            )

    # --- INPUTS ---
    print(f"\n{'─' * W}")
    print(f"  INPUTS (contexto 1D lookahead, recalc_window={rw})")
    print(f"{'─' * W}")
    print(header_row)
    print("-" * W)

    input_dir = "inputs"
    g_n = g_bs = g_state = g_hdr = g_pad = g_total = 0
    for i in range(1, 9):
        path = os.path.join(input_dir, f"input_{i}.txt")
        if not os.path.exists(path):
            print(f"  input_{i}.txt não encontrado, pulando.")
            continue
        r = run_one(path, rw)
        print_row("INPUT_" + str(i), r)
        g_n += r["n"]; g_bs += r["bits_bs"]; g_state += r["bits_state"]
        g_hdr += r["bits_hdr"]; g_pad += r["bits_pad"]; g_total += r["bits_total"]
    print_global(g_n, g_bs, g_state, g_hdr, g_pad, g_total)

    # --- PLANOS DE BITS ---
    print(f"\n{'─' * W}")
    print(f"  PLANOS DE BITS (contexto 1D lookahead, recalc_window={rw})")
    print(f"{'─' * W}")
    print(header_row)
    print("-" * W)

    plano_dir = "Plano_de_Bits"
    g_n = g_bs = g_state = g_hdr = g_pad = g_total = 0
    for p in range(8):
        path = os.path.join(plano_dir, f"plano_bit_{p}.txt")
        if not os.path.exists(path):
            print(f"  plano_bit_{p}.txt não encontrado, pulando.")
            continue
        r = run_one(path, rw)
        print_row("PLANO_" + str(p), r)
        g_n += r["n"]; g_bs += r["bits_bs"]; g_state += r["bits_state"]
        g_hdr += r["bits_hdr"]; g_pad += r["bits_pad"]; g_total += r["bits_total"]
    print_global(g_n, g_bs, g_state, g_hdr, g_pad, g_total)

    print(f"\n{'=' * W}")
    print("  Processamento concluído.")
    print("=" * W)


if __name__ == "__main__":
    main()

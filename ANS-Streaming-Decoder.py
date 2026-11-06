import os
import argparse
from collections import deque

from context_model import ContextModel, NUM_CONTEXTS_1D


# ---------------------------------------------------------------------------
# rANS primitivos (decoder)
# ---------------------------------------------------------------------------

def _D_rANS(state: int, counts: list[int]) -> tuple[int, int]:
    """
    Decodifica um símbolo do estado rANS.
    counts = [c0, c1]. Retorna (símbolo, estado_anterior_não_normalizado).
    """
    M  = counts[0] + counts[1]
    cs = [0, counts[0]]      # frequências acumuladas: cs[0]=0, cs[1]=c0
    slot = state % M
    # Encontra o símbolo cujo intervalo cobre 'slot'
    s = 1 if slot >= counts[0] else 0
    prev = (state // M) * counts[s] + slot - cs[s]
    return s, prev


def decode_stream(bitstream_str: str, final_state: int, num_symbols: int,
                  model: ContextModel,
                  recalc_window: int = 0) -> list[int]:
    bits = deque(map(int, bitstream_str[::-1]))
    decoded      = [0] * num_symbols
    state        = final_state
    last_decoded = 0

    for i in range(num_symbols - 1, -1, -1):
        ctx = last_decoded

        blk    = i // recalc_window if recalc_window > 0 else None
        counts = model.get_counts(ctx, blk)
        s, prev = _D_rANS(state, counts)
        M = counts[0] + counts[1]
        while prev < M and bits:
            prev = (prev << 1) | bits.popleft()

        state        = prev
        decoded[i]   = s
        last_decoded = s

    return decoded


# ---------------------------------------------------------------------------
# Leitura do arquivo comprimido
# ---------------------------------------------------------------------------

def load_encoded(path: str) -> dict:
    """Lê o arquivo no formato do encoder e retorna campos como dict."""
    with open(path, "r") as f:
        lines = f.readlines()
    if len(lines) < 6:
        raise ValueError(f"Arquivo '{path}' tem formato inválido (≥ 6 linhas esperadas).")
    return {
        "num_symbols":   int(lines[0].strip()),
        "mode":          lines[1].strip(),
        "recalc_window": int(lines[2].strip()),
        "bitstream":     lines[3].strip(),
        "final_state":   int(lines[4].strip()),
        "headers_hex":   lines[5].strip(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ANS Streaming Decoder — Contextual")
    parser.add_argument("--encoded", default="input_encoded.bin", help="Arquivo comprimido")
    parser.add_argument("--output",  default="output.txt",        help="Arquivo de saída")
    parser.add_argument("--verify",  default="",                  help="Arquivo original para verificação")
    args = parser.parse_args()

    if not os.path.exists(args.encoded):
        print(f"Erro: '{args.encoded}' não encontrado.")
        return

    print("=" * 72)
    print("  ANS STREAMING DECODER")
    print("=" * 72)

    data = load_encoded(args.encoded)
    num_symbols   = data["num_symbols"]
    mode          = data["mode"]
    recalc_window = data["recalc_window"]
    bitstream     = data["bitstream"]
    final_state   = data["final_state"]
    headers_hex   = data["headers_hex"]

    n_ctx = NUM_CONTEXTS_1D

    print(f"Símbolos a decodificar : {num_symbols}")
    print(f"Modo                   : {mode}")
    print(f"Contexto               : 1D (lookahead-1)")
    print(f"Recalc window          : {recalc_window}")
    print(f"Bits no bitstream      : {len(bitstream)}")
    print(f"Estado final           : {final_state}")

    model = ContextModel(mode=mode, num_contexts=n_ctx,
                         recalc_window=recalc_window)
    model.load_static_headers(headers_hex)

    import time
    t0 = time.time()
    decoded = decode_stream(bitstream, final_state, num_symbols, model,
                            recalc_window=recalc_window)

    t1 = time.time()

    # Salva resultado
    with open(args.output, "w") as f:
        f.write(" ".join(map(str, decoded)))

    print(f"\nSequência decodificada salva em '{args.output}' ({len(decoded)} símbolos).")
    print(f"Tempo de decodificação: {t1 - t0:.6f}s")

    # Verificação de integridade
    verify_path = args.verify
    if not verify_path and os.path.exists("input.txt"):
        verify_path = "input.txt"

    if verify_path and os.path.exists(verify_path):
        with open(verify_path, "r") as f:
            content = f.read().replace(",", " ").replace("\n", " ").replace("\r", "")
        tokens = content.split()
        if all(len(t) == 1 for t in tokens if t):
            original = [int(x) for x in tokens if x in ("0", "1")]
        else:
            original = [int(c) for c in content if c in ("0", "1")]

        if decoded == original:
            print("\n" + "=" * 72)
            print("  ✓  SUCESSO: sequência decodificada é 100% IDÊNTICA à original!")
            print("=" * 72)
        else:
            print("\n" + "!" * 72)
            print("  ✗  ERRO: sequência decodificada DIVERGE da original!")
            diffs = [i for i, (a, b) in enumerate(zip(original, decoded)) if a != b]
            print(f"  Divergências: {len(diffs)} posições. Primeiras: {diffs[:10]}")
            print("!" * 72)
    else:
        print("\nAviso: arquivo original não informado; verificação ignorada.")


if __name__ == "__main__":
    main()

import numpy as np
import time
import os
import argparse

from context_model import ContextModel, NUM_CONTEXTS_1D

# ---------------------------------------------------------------------------
# rANS primitivos
# ---------------------------------------------------------------------------

def _C_rANS(s: int, state: int, counts: list[int]) -> int:
    """Codifica símbolo s no estado rANS. counts = [c0, c1]."""
    M    = counts[0] + counts[1]
    cs   = sum(counts[:s])   # frequência acumulada até s
    fs   = counts[s]
    return (state // fs) * M + cs + (state % fs)


def _encode_symbol(state: int, s: int, counts: list[int],
                   bitstream: list[int]) -> int:
    """
    Normaliza o estado e codifica o símbolo s.
    Emite bits para manter o estado no intervalo válido.
    """
    fs = counts[s]
    # Normalização: emite bits enquanto estado >= 2 * f_s
    while state >= 2 * fs:
        bitstream.append(state & 1)
        state >>= 1
    return _C_rANS(s, state, counts)


# ---------------------------------------------------------------------------
# Geração das tabelas tANS (tans_tables.h) a partir do rANS acima
#
# Cada entrada é o encoder rANS streaming (_encode_symbol, equação (7) do
# tutorial LASCAS 2025) aplicado a um estado x em [L, 2L-1], um símbolo s e uma
# configuração (f0, L-f0), com M = L, F(0)=f0, F(1)=L-f0, C(0)=0, C(1)=f0.
# O decoder em C monta sua tabela inversa a partir destas mesmas entradas
# (equivalente à equação (8) do rANS).
# ---------------------------------------------------------------------------

def tabela_rans(L, f0):
    """Para a cfg (f0, L-f0) devolve, por símbolo, listas [novo_estado, valor_bits, nbits]
    indexadas por (estado - L)."""
    counts = [f0, L - f0]
    out = {0: [], 1: []}
    for s in (0, 1):
        for x in range(L, 2 * L):
            emitidos = []                                   # ordem de emissão (LSB primeiro)
            novo = _encode_symbol(x, s, counts, emitidos)   # <- rANS do projeto
            k = len(emitidos)
            # o writer em C grava o valor MSB primeiro: 1º bit emitido = bit mais alto
            valor = 0
            for b in emitidos:
                valor = (valor << 1) | b
            out[s].append((novo, valor, k))
    return out


def fmt_linha(vals, comentario):
    return "    {" + ", ".join(vals) + "}, /* " + comentario + " */\n"


def gerar(L, freqs):
    nb = (L - 1).bit_length()          # ceil(log2(L))
    flush = nb
    tabs = [tabela_rans(L, f0) for f0 in freqs]
    desc = [f"cfg {i} : P(0) = {f0}/{L} = {100*f0/L:.0f}%,  P(1) = {L-f0}/{L} = {100*(L-f0)/L:.0f}%"
            for i, f0 in enumerate(freqs)]
    n = len(freqs)
    h = []
    h.append("/* =============================================================================\n")
    h.append(" * tans_tables.h  -  Tabelas pré-computadas para codificação tANS estática\n")
    h.append(" *\n")
    h.append(" * ARQUIVO GERADO por ANS-Streaming Encoder.py (--gerar-tabelas) - não editar à mão.\n")
    h.append(" *\n")
    h.append(" * Alfabeto binário: símbolo 0 e símbolo 1\n")
    h.append(f" * RANGE = {L}  →  espaço de estados [{L}, {2*L-1}]  (índices 0..{L-1})\n")
    h.append(f" * FLUSH_BITS = {flush}  (ceil(log2(RANGE)) bits para salvar o estado final)\n")
    h.append(" *\n")
    h.append(f" * Configurações disponíveis (RANGE == {L}):\n")
    for d in desc:
        h.append(f" *   {d}\n")
    h.append(" *\n")
    h.append(" * Como as tabelas foram geradas (pelo rANS)\n")
    h.append(" * ─────────────────────────────────────────\n")
    h.append(" * Cada entrada é o encoder rANS streaming do projeto (run_all.py) aplicado a\n")
    h.append(" * um estado x ∈ [RANGE, 2·RANGE-1] e a um símbolo s, com M = RANGE,\n")
    h.append(" * F(0) = f0, F(1) = M - f0, C(0) = 0, C(1) = f0:\n")
    h.append(" *   1. Renormalização: enquanto x >= 2·F(s), emite x & 1 e faz x >>= 1.\n")
    h.append(" *      Os bits saem LSB primeiro; o valor guardado é o 1º bit emitido como\n")
    h.append(" *      bit mais alto (o writer em C grava o valor MSB primeiro).\n")
    h.append(" *   2. Equação (7): novo estado = (x / F(s))·M + C(s) + (x mod F(s)).\n")
    h.append(" * Resultado: cada símbolo ocupa um bloco contíguo de estados (layout do\n")
    h.append(" * tutorial LASCAS 2025). Bits emitidos usam 0xFF (EMPTY) quando nenhum bit sai.\n")
    h.append(" *\n")
    h.append(" * Convenção de nomes:\n")
    h.append(" *   a_*  →  símbolo 0     b_*  →  símbolo 1\n")
    h.append(" *   *_table      novo estado após a transição\n")
    h.append(" *   *_bitstream  bits emitidos (0xFF = nenhum bit)\n")
    h.append(" *   *_nbits      número de bits emitidos\n")
    h.append(" * ============================================================================= */\n\n")
    h.append("#ifndef TANS_TABLES_H\n#define TANS_TABLES_H\n\n#include <stdint.h>\n\n")
    h.append(f"#define RANGE      {L}    /* Tamanho do espaço de estados L: estados em [L, 2L-1] */\n")
    h.append(f"#define FLUSH_BITS  {flush}    /* Bits para armazenar o estado final: ceil(log2(RANGE)) */\n")
    h.append("#define EMPTY      0xFF  /* Sentinela: nenhum bit emitido nesta transição */\n\n")

    def bloco(nome, sym, campo, titulo, tipo):
        h.append(f"/* {titulo} */\n")
        h.append(f"static const uint8_t {nome}_range{L}[{n}][{L}] = {{\n")
        for i, f0 in enumerate(freqs):
            ent = tabs[i][sym]
            if campo == "ns":
                vals = [str(e[0]) for e in ent]
            elif campo == "bits":
                vals = ["0xFF" if e[2] == 0 else f"0x{e[1]:02X}" for e in ent]
            else:
                vals = [str(e[2]) for e in ent]
            h.append(fmt_linha(vals, f"cfg {i}: P(0)={f0}/{L}"))
        h.append("};\n\n")

    bloco("a", 0, "ns",   "Novo estado ao encodar símbolo 0", "")
    bloco("a_bitstream", 0, "bits", "Bits emitidos ao encodar símbolo 0 (0xFF = nenhum bit)", "")
    bloco("a_nbits", 0, "nb", "Número de bits emitidos ao encodar símbolo 0", "")
    bloco("b", 1, "ns",   "Novo estado ao encodar símbolo 1", "")
    bloco("b_bitstream", 1, "bits", "Bits emitidos ao encodar símbolo 1 (0xFF = nenhum bit)", "")
    bloco("b_nbits", 1, "nb", "Número de bits emitidos ao encodar símbolo 1", "")
    h.append("/* Frequência do símbolo 0 por configuração (usada em select_cfg) */\n")
    h.append(f"static const int freq_a_range{L}[{n}] = {{" + ", ".join(map(str, freqs)) + "};\n\n")
    h.append("#endif /* TANS_TABLES_H */\n")
    return "".join(h)


# ---------------------------------------------------------------------------
# Encoder contextual — estado contínuo
# ---------------------------------------------------------------------------

def encode_stream(symbols: list[int], model: ContextModel,
                  recalc_window: int = 0) -> tuple[str, int]:
    n = len(symbols)
    if n == 0:
        return "", 0

    def get_ctx(i: int) -> int:
        return symbols[i + 1] if i + 1 < n else 0

    ctx0    = get_ctx(0)
    counts0 = model.get_counts(ctx0, 0)
    state   = counts0[0] + counts0[1]
    bitstream: list[int] = []

    for i in range(n):
        ctx    = get_ctx(i)
        blk    = i // recalc_window if recalc_window > 0 else None
        counts = model.get_counts(ctx, blk)
        state  = _encode_symbol(state, symbols[i], counts, bitstream)

    return "".join(map(str, bitstream)), state


# ---------------------------------------------------------------------------
# Leitura de input
# ---------------------------------------------------------------------------

def load_symbols(path: str) -> list[int]:
    with open(path, "r") as f:
        content = f.read().replace(",", " ").replace("\n", " ").replace("\r", "")
    tokens = content.split()
    if all(len(t) == 1 for t in tokens if t):
        return [int(x) for x in tokens if x in ("0", "1")]
    return [int(c) for c in content if c in ("0", "1")]


# ---------------------------------------------------------------------------
# Salvar arquivo comprimido
# ---------------------------------------------------------------------------

def save_encoded(path: str, num_symbols: int, mode: str, recalc_window: int,
                 bitstream: str, final_state: int, headers_hex: str) -> None:
    """
    Formato do arquivo comprimido (texto, um campo por linha):
      Linha 0: num_symbols
      Linha 1: mode
      Linha 2: recalc_window
      Linha 3: bitstream (string de 0s e 1s)
      Linha 4: final_state
      Linha 5: headers_hex
    """
    with open(path, "w") as f:
        f.write(f"{num_symbols}\n")
        f.write(f"{mode}\n")
        f.write(f"{recalc_window}\n")
        f.write(f"{bitstream}\n")
        f.write(f"{final_state}\n")
        f.write(f"{headers_hex}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ANS Streaming Encoder — Contextual")
    parser.add_argument("--input",         default="input.txt",        help="Arquivo de entrada")
    parser.add_argument("--output",        default="input_encoded.bin", help="Arquivo de saída")
    parser.add_argument("--mode",          default="static", choices=["static"])
    parser.add_argument("--recalc-window", type=int, default=1000,     help="Janela de recalibração")
    parser.add_argument("--gerar-tabelas", action="store_true",
                        help="Gera tans_tables.h a partir do rANS e sai")
    parser.add_argument("--range", type=int, default=10,
                        help="RANGE (L) das tabelas geradas (padrão: 10)")
    parser.add_argument("--freqs", default="9,1",
                        help="f0 de cada cfg, ex.: 9,1 (padrão)")
    parser.add_argument("--saida", default="tans_tables.h",
                        help="Arquivo de saída das tabelas (padrão: tans_tables.h)")
    args = parser.parse_args()

    if args.gerar_tabelas:
        freqs = [int(x) for x in args.freqs.split(",")]
        assert all(1 <= f < args.range for f in freqs), "cada f0 deve estar entre 1 e RANGE-1"
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(gerar(args.range, freqs))
        print(f"{args.saida} gerado: RANGE={args.range}, cfgs (f0) = {freqs}")
        return

    if not os.path.exists(args.input):
        print(f"Erro: arquivo '{args.input}' não encontrado.")
        return

    print("=" * 72)
    print(f"  ANS STREAMING ENCODER  |  mode={args.mode}  |  "
          f"recalc_window={args.recalc_window}")
    print("=" * 72)

    symbols = load_symbols(args.input)
    # NOTA CONTABILIDADE: 'num_symbols_real' é o tamanho SEM padding.
    # A versão anterior usava o bloco com padding como denominador, inflando
    # a taxa reportada. Aqui usamos apenas o tamanho real da entrada.
    num_symbols_real = len(symbols)
    print(f"Símbolos lidos: {num_symbols_real}")

    # Contexto 1D (2 ctx) — lookahead
    n_ctx = NUM_CONTEXTS_1D
    print(f"Contexto: 1D (lookahead-1)  |  {n_ctx} contextos")

    # Pré-varredura por bloco
    model = ContextModel(mode="static", num_contexts=n_ctx,
                         recalc_window=args.recalc_window)

    n = len(symbols)
    rw = args.recalc_window
    n_blocks = (n + rw - 1) // rw

    def get_ctx_prescan(i: int) -> int:
        return symbols[i + 1] if i + 1 < n else 0

    block_freqs = []
    for b in range(n_blocks):
        counts = [[1, 1] for _ in range(n_ctx)]
        start = b * rw
        end   = min(start + rw, n)
        for i in range(start, end):
            ctx = get_ctx_prescan(i)
            counts[ctx][symbols[i]] += 1
        block_freqs.append(model._normalize(counts))
    model.set_block_freqs(block_freqs)
    print(f"Blocos: {n_blocks} (recalc_window={rw})")

    t0 = time.time()
    bitstream, final_state = encode_stream(symbols, model, recalc_window=rw)
    t1 = time.time()

    headers_hex = model.serialize_static_headers()

    # Calcula métricas
    bits_bitstream   = len(bitstream)
    bits_state       = final_state.bit_length() if final_state > 0 else 1
    bits_header_oh   = model.header_overhead_bits()
    # CONTABILIDADE CORRETA: denominador = num_symbols_real (sem padding)
    # Overhead do header é parte do custo total transmitido
    bits_total_tx    = bits_bitstream + bits_state + bits_header_oh
    taxa_compressao  = (1.0 - bits_total_tx / num_symbols_real) * 100 \
                       if num_symbols_real > 0 else 0.0

    # Entropia global
    c0 = symbols.count(0); c1 = symbols.count(1)
    p0 = c0 / num_symbols_real; p1 = c1 / num_symbols_real
    H  = 0.0
    if p0 > 0: H -= p0 * np.log2(p0)
    if p1 > 0: H -= p1 * np.log2(p1)

    print(f"\nEntropia global H = {H:.6f} bits/símbolo")
    print(f"Limite teórico (sem contexto): {H * num_symbols_real:.1f} bits totais\n")

    print("-" * 72)
    print(f"{'Métrica':<40} {'Valor':>12} {'Unidade'}")
    print("-" * 72)
    print(f"{'Símbolos originais (sem padding)':<40} {num_symbols_real:>12} bits")
    print(f"{'Bits no bitstream rANS':<40} {bits_bitstream:>12} bits")
    print(f"{'Bits do estado final':<40} {bits_state:>12} bits")
    print(f"{'Overhead de cabeçalhos':<40} {bits_header_oh:>12} bits")
    print(f"{'Total transmitido':<40} {bits_total_tx:>12} bits")
    # CONTABILIDADE CORRETA (comentário)
    # taxa = (original - total_tx) / original   ← usa original SEM padding
    print(f"{'Taxa de compressão':<40} {taxa_compressao:>11.2f}%")
    print(f"{'Tempo de codificação':<40} {t1 - t0:>11.6f}s")
    print("-" * 72)

    save_encoded(args.output, num_symbols_real, args.mode, args.recalc_window,
                 bitstream, final_state, headers_hex)

    print(f"\nArquivo salvo: '{args.output}'")
    print("=" * 72)


if __name__ == "__main__":
    main()
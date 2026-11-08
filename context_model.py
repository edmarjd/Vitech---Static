NUM_CONTEXTS_1D = 2  # 0 e 1 (bit anterior/próximo)

PRECISION_BITS = 5  # bits de precisão
PRECISION = 1 << PRECISION_BITS  # 32


class ContextModel:

    def __init__(
        self, mode: str = "static", num_contexts: int = NUM_CONTEXTS_1D, recalc_window: int = 1000
    ):
        if mode != "static":
            raise ValueError("Único modo suportado: 'static'")
        self.mode = mode
        self.num_contexts = num_contexts
        self.recalc_window = recalc_window
        self._sym_count = 0
        self._headers: list[list[int]] = []
        self._win_counts = [[1, 1] for _ in range(num_contexts)]
        # Prior de Laplace inicial
        self._freq = [[1, 1] for _ in range(num_contexts)]
        self._block_freqs = []

    def set_block_freqs(self, block_freqs: list) -> None:
        """Define tabelas de frequência separadas por bloco."""
        self._block_freqs = block_freqs
        self._block_headers = [[c[0] for c in bf] for bf in block_freqs]
        self._no_recalc = True
        if block_freqs:
            self._freq = block_freqs[0]

    def get_counts(self, ctx: int, block_idx: int = None) -> list[int]:
        """Retorna [c0, c1] para uso no C_rANS / D_rANS."""
        if block_idx is not None and self._block_freqs:
            idx = min(block_idx, len(self._block_freqs) - 1)
            return self._block_freqs[idx][ctx]
        return self._freq[ctx]

    def update_after_symbol(self, ctx: int, sym: int) -> bool:
        """Sem recalibração intermediária (_no_recalc=True). Sempre retorna False."""
        return False

    def advance_window_decoder(self) -> None:
        """Sem recalibração intermediária — tabela fixa. No-op."""
        return

    def serialize_static_headers(self) -> str:
        """Serializa cabeçalho(s) como string hex (um por bloco)."""
        if hasattr(self, '_block_headers') and self._block_headers:
            all_headers = self._block_headers
        else:
            init = getattr(self, "_init_header", None)
            all_headers = ([init] if init else []) + self._headers
        if not all_headers:
            return ""
        bits: list[int] = []
        for hdr in all_headers:
            for c0n in hdr:
                for b in range(PRECISION_BITS - 1, -1, -1):
                    bits.append((c0n >> b) & 1)
        while len(bits) % 8:
            bits.append(0)
        val = int("".join(map(str, bits)), 2)
        return format(val, f"0{len(bits) // 4}x")

    def load_static_headers(self, hex_str: str) -> None:
        """Carrega cabeçalho(s) e reconstrói tabelas por bloco."""
        if not hex_str:
            self._headers = []
            self._block_freqs = []
            return
        n_bits = len(hex_str) * 4
        val = int(hex_str, 16)
        bits = [(val >> (n_bits - 1 - i)) & 1 for i in range(n_bits)]
        bph = self.num_contexts * PRECISION_BITS
        self._headers = []
        pos = 0
        while pos + bph <= len(bits):
            hdr = []
            for _ in range(self.num_contexts):
                c0n = 0
                for _ in range(PRECISION_BITS):
                    c0n = (c0n << 1) | bits[pos]
                    pos += 1
                hdr.append(c0n)
            if any(v > 0 for v in hdr):
                self._headers.append(hdr)
        # Reconstrói tabelas de frequência por bloco
        self._block_freqs = []
        for hdr in self._headers:
            freq = []
            for c0n in hdr:
                c0n = max(1, min(PRECISION - 1, c0n))
                freq.append([c0n, PRECISION - c0n])
            self._block_freqs.append(freq)
        if self._block_freqs:
            self._freq = self._block_freqs[0]
        else:
            # BUG8: cabeçalho corrompido ou vazio — avisa e mantém prior de Laplace
            import warnings

            warnings.warn(
                "load_static_headers: nenhum bloco válido encontrado no cabeçalho hex. "
                "Usando prior de Laplace [[1,1],[1,1]]. A decodificação pode estar errada.",
                RuntimeWarning,
                stacklevel=2,
            )
        self._no_recalc = True

    def header_overhead_bits(self) -> int:
        """Bits de overhead (num_blocos × num_contexts × PRECISION_BITS (5 bits))."""
        n_blocks = max(1, len(self._block_freqs))
        return n_blocks * self.num_contexts * PRECISION_BITS

    def padding_bits(self) -> int:
        """Bits de preenchimento adicionados para alinhar o cabeçalho a 8 bits."""
        raw = self.header_overhead_bits()
        # BUG12: se raw==0 (sem blocos), não há padding
        if raw == 0:
            return 0
        remainder = raw % 8
        return (8 - remainder) % 8

    def _normalize(self, counts: list[list[int]]) -> list[list[int]]:
        """Normaliza contagens para soma = PRECISION; garante c0, c1 >= 1."""
        result = []
        for c0, c1 in counts:
            total = c0 + c1
            c0n = round(c0 * PRECISION / total)
            c0n = max(1, min(PRECISION - 1, c0n))
            result.append([c0n, PRECISION - c0n])
        return result

    def _apply_header(self, hdr: list[int]) -> None:
        self._freq = []
        for c0n in hdr:
            c0n = max(1, min(PRECISION - 1, c0n))
            self._freq.append([c0n, PRECISION - c0n])
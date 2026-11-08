#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/*
 CONFIGURAÇÃO GLOBAL
 */

#include "tans_tables.h"

#define MAX_SYMBOLS 12000000 /* ate ~12 Mpixels por plano (DIV2K cabe) */
#define BITSTREAM_CAPACITY MAX_SYMBOLS

/* Tamanho de bloco — usar -DBLOCK_SIZE=N na compilação */
#ifndef BLOCK_SIZE
#define BLOCK_SIZE 10000
#endif

/*
 DEBUG
 */

#define DEBUG 0

#if DEBUG
#define DBG_PRINTF(...) printf(__VA_ARGS__)
#else
#define DBG_PRINTF(...)
#endif

/*
 BUFFERS ESTÁTICOS
 */

static int symbols_buffer[MAX_SYMBOLS];
static uint8_t global_bitstream_buffer[BITSTREAM_CAPACITY];

/*
 ESTRUTURAS
 */

typedef struct {
    uint8_t *buffer;
    size_t byte_pos;
    int bit_pos;
    int total_bits_written;
    size_t capacity;
    int overflow; /* BUG10: flag de overflow do buffer */
} BitstreamWriter;

typedef struct {
    uint32_t state;
} AnsState;

typedef struct {
    AnsState state;
} AnsContext;

/*
 BITSTREAM
 */

void bitstream_init(BitstreamWriter *stream) {
    memset(global_bitstream_buffer, 0, BITSTREAM_CAPACITY);
    stream->buffer = global_bitstream_buffer;
    stream->byte_pos = 0;
    stream->bit_pos = 7;
    stream->total_bits_written = 0;
    stream->capacity = BITSTREAM_CAPACITY;
    stream->overflow = 0;
}

void bitstream_write_bits(BitstreamWriter *stream, uint32_t bits, int nbits) {
    for (int i = nbits - 1; i >= 0; i--) {
        if (stream->byte_pos >= stream->capacity) {
            if (!stream->overflow) {
                fprintf(stderr,
                        "ERRO: bitstream cheio — arquivo de saída pode estar "
                        "corrompido.\n");
                stream->overflow = 1;
            }
            return;
        }
        uint8_t bit = (bits >> i) & 1;
        if (bit) {
            stream->buffer[stream->byte_pos] |= (1 << stream->bit_pos);
        }
        stream->total_bits_written++;
        stream->bit_pos--;
        if (stream->bit_pos < 0) {
            stream->bit_pos = 7;
            stream->byte_pos++;
        }
    }
}

/* Retorna a entrada de tabela dado um cfg explícito (não ctx_idx) */
static inline void get_table_entry(int cfg, int state_idx, int symbol,
                                   uint8_t *new_state_out, uint8_t *bits_out,
                                   uint8_t *nbits_out) {
#if RANGE == 10
    const uint8_t(*at)[10] = a_range10;
    const uint8_t(*ab)[10] = a_bitstream_range10;
    const uint8_t(*an)[10] = a_nbits_range10;
    const uint8_t(*bt)[10] = b_range10;
    const uint8_t(*bb)[10] = b_bitstream_range10;
    const uint8_t(*bn)[10] = b_nbits_range10;
#elif RANGE == 9
    const uint8_t(*at)[9] = a_range9;
    const uint8_t(*ab)[9] = a_bitstream_range9;
    const uint8_t(*an)[9] = a_nbits_range9;
    const uint8_t(*bt)[9] = b_range9;
    const uint8_t(*bb)[9] = b_bitstream_range9;
    const uint8_t(*bn)[9] = b_nbits_range9;
#elif RANGE == 8
    const uint8_t(*at)[8] = a_range8;
    const uint8_t(*ab)[8] = a_bitstream_range8;
    const uint8_t(*an)[8] = a_nbits_range8;
    const uint8_t(*bt)[8] = b_range8;
    const uint8_t(*bb)[8] = b_bitstream_range8;
    const uint8_t(*bn)[8] = b_nbits_range8;
#elif RANGE == 6
    const uint8_t(*at)[6] = a_range6;
    const uint8_t(*ab)[6] = a_bitstream_range6;
    const uint8_t(*an)[6] = a_nbits_range6;
    const uint8_t(*bt)[6] = b_range6;
    const uint8_t(*bb)[6] = b_bitstream_range6;
    const uint8_t(*bn)[6] = b_nbits_range6;
#elif RANGE == 4
    const uint8_t(*at)[4] = a_range4;
    const uint8_t(*ab)[4] = a_bitstream_range4;
    const uint8_t(*an)[4] = a_nbits_range4;
    const uint8_t(*bt)[4] = b_range4;
    const uint8_t(*bb)[4] = b_bitstream_range4;
    const uint8_t(*bn)[4] = b_nbits_range4;
#else
    const uint8_t(*at)[2] = a_range2;
    const uint8_t(*ab)[2] = a_bitstream_range2;
    const uint8_t(*an)[2] = a_nbits_range2;
    const uint8_t(*bt)[2] = b_range2;
    const uint8_t(*bb)[2] = b_bitstream_range2;
    const uint8_t(*bn)[2] = b_nbits_range2;
#endif

    if (symbol == 0) {
        *new_state_out = at[cfg][state_idx];
        *bits_out = ab[cfg][state_idx];
        *nbits_out = an[cfg][state_idx];
    } else {
        *new_state_out = bt[cfg][state_idx];
        *bits_out = bb[cfg][state_idx];
        *nbits_out = bn[cfg][state_idx];
    }
}

/*
 Seleciona o melhor CONFIG válido para P(0) = c0/(c0+c1)
 usando os configs válidos do RANGE atual.
*/
static int select_cfg(int c0, int c1) {
#if RANGE == 10
    int cfgs[] = {0, 1};
    int n = 2;
    const int *freqs = freq_a_range10;
#elif RANGE == 9
    int cfgs[] = {0, 1, 2, 3, 4, 5, 6, 7};
    int n = 8;
    const int *freqs = freq_a_range9;
#elif RANGE == 8
    int cfgs[] = {0, 1, 2, 3, 4, 5, 6};
    int n = 7;
    const int *freqs = freq_a_range8;
#elif RANGE == 6
    int cfgs[] = {2, 3, 4};
    int n = 3;
    const int *freqs = freq_a_range6;
#elif RANGE == 4
    int cfgs[] = {0, 1, 2};
    int n = 3;
    const int *freqs = freq_a_range4;
#else
    int cfgs[] = {0};
    int n = 1;
    const int freqs[] = {1};
#endif

    if (c0 + c1 == 0) {
        return cfgs[n - 1]; /* padrão 50% */
    }
    double p0 = (double)c0 / (c0 + c1);

    int best = cfgs[n - 1];
    double best_diff = 999.0;
    for (int i = 0; i < n; i++) {
        int cfg_idx = cfgs[i];
        double target_p = (double)freqs[cfg_idx] / RANGE;
        double diff = fabs(p0 - target_p);
        if (diff < best_diff) {
            best_diff = diff;
            best = cfg_idx;
        }
    }
    return best;
}

void ans_init(AnsContext *context) {
    context->state.state = RANGE;
}

/* Encode com cfg explícito */
void ans_encode_symbol_cfg(AnsContext *context, int symbol,
                           BitstreamWriter *stream, int cfg) {
    uint32_t state = context->state.state;
    int state_idx = state - RANGE;
    uint8_t new_state, bits_out, nbits;
    get_table_entry(cfg, state_idx, symbol, &new_state, &bits_out, &nbits);
    if (nbits > 0 && bits_out != EMPTY) {
        bitstream_write_bits(stream, bits_out, nbits);
    }
    context->state.state = new_state;
}

/*
 PROCESS FILE
 */

typedef struct {
    uint8_t cfg0;
    uint8_t cfg1;
    uint32_t blk_bytes;
    uint32_t bits_used; /* bits escritos no bloco (com estado e stop) */
    size_t offset;
} BlockMeta;

static BlockMeta block_metas[MAX_SYMBOLS / 10 + 100];
static uint8_t raw_buffer[BITSTREAM_CAPACITY];

void process_file(const char *filename) {

    FILE *file = fopen(filename, "r");

    if (!file) {

        perror("fopen entrada");

        return;
    }

    int symbol_count = 0;
    int count0 = 0, count1 = 0;
    int symbol;

    while (fscanf(file, "%d", &symbol) == 1) {

        if (symbol_count >= MAX_SYMBOLS) {

            fprintf(stderr, "ERRO: muitos simbolos (limite %d)\n", MAX_SYMBOLS);

            fclose(file);

            return;
        }

        if (symbol == 0 || symbol == 1) {

            symbols_buffer[symbol_count++] = symbol;
            if (symbol == 0) {
                count0++;
            } else {
                count1++;
            }

        } else {

            fprintf(
                stderr,
                "AVISO: símbolo inválido '%d' ignorado (esperado 0 ou 1).\n",
                symbol);
        }
    }

    fclose(file);

    if (symbol_count == 0) {
        fprintf(stderr, "AVISO: arquivo vazio.\n");
        return;
    }

    /* Gera nome do arquivo de saída */
    char output_filename[512];
    const char *slash = strrchr(filename, '/');
    const char *dot = strrchr(filename, '.');
    int base_len = (dot && (!slash || dot > slash)) ? (int)(dot - filename)
                                                    : (int)strlen(filename);
    if (base_len > 490) {
        base_len = 490;
    }
    strncpy(output_filename, filename, (size_t)base_len);
    strcpy(output_filename + base_len, "_encoded.bin");

    FILE *fout = fopen(output_filename, "wb");
    if (!fout) {
        perror("fopen saida");
        return;
    }

    /* 1. Codificação tANS por Blocos Independentes */
    uint32_t num_blocks = (symbol_count + BLOCK_SIZE - 1) / BLOCK_SIZE;
    size_t total_tans_payload = 0;

    for (uint32_t b = 0; b < num_blocks; b++) {
        int bstart = b * BLOCK_SIZE;
        int bend = bstart + BLOCK_SIZE;
        if (bend > symbol_count) {
            bend = symbol_count;
        }

        /* Mede proporções contextuais 1D no bloco independente */
        int c00 = 0, c01 = 0, c10 = 0, c11 = 0;
        for (int i = bstart; i < bend; i++) {
            int s = symbols_buffer[i];
            int nxt = (i + 1 < bend) ? symbols_buffer[i + 1] : 0;
            if (nxt == 0) {
                if (s == 0) {
                    c00++;
                } else {
                    c01++;
                }
            } else {
                if (s == 0) {
                    c10++;
                } else {
                    c11++;
                }
            }
        }

        int cfg0 = select_cfg(c00, c01);
        int cfg1 = select_cfg(c10, c11);

        AnsContext ctx_blk;
        ans_init(&ctx_blk);

        BitstreamWriter bs;
        bs.buffer = global_bitstream_buffer + total_tans_payload;
        bs.byte_pos = 0;
        bs.bit_pos = 7;
        bs.total_bits_written = 0;
        bs.capacity = BITSTREAM_CAPACITY - total_tans_payload;
        bs.overflow = 0;
        memset(bs.buffer, 0, (bend - bstart) * 2 + 64);

        for (int i = bstart; i < bend; i++) {
            int nxt = (i + 1 < bend) ? symbols_buffer[i + 1] : 0;
            int cfg = (nxt == 0) ? cfg0 : cfg1;
            ans_encode_symbol_cfg(&ctx_blk, symbols_buffer[i], &bs, cfg);
        }

        if (bs.overflow) {
            fprintf(stderr, "ERRO: overflow no buffer de bits (bloco %u)\n", b);
            fclose(fout);
            return;
        }

        /* Flush do estado final + stop bit */
        uint32_t off = ctx_blk.state.state - RANGE;
        bitstream_write_bits(&bs, off, FLUSH_BITS);
        bitstream_write_bits(&bs, 1, 1); /* stop bit */

        uint32_t blk_bytes = (uint32_t)((bs.total_bits_written + 7) / 8);
        block_metas[b].cfg0 = (uint8_t)cfg0;
        block_metas[b].cfg1 = (uint8_t)cfg1;
        block_metas[b].blk_bytes = blk_bytes;
        block_metas[b].bits_used = (uint32_t)bs.total_bits_written;
        block_metas[b].offset = total_tans_payload;

        total_tans_payload += blk_bytes;
    }

    /* Header global: 10B -> [num_symbols (4B)] [RANGE (1B)] [mode (1B)]
   * [num_blocks (4B)] */
    size_t total_tans_bytes = 10 + (size_t)num_blocks * 6 + total_tans_payload;
    size_t raw_payload_bytes = (symbol_count + 7) / 8;
    size_t total_raw_bytes = 10 + raw_payload_bytes;

    uint8_t mode = (total_tans_bytes < total_raw_bytes) ? 1 : 0;
    size_t final_total_bytes = (mode == 1) ? total_tans_bytes : total_raw_bytes;

    uint32_t ns = (uint32_t)symbol_count;
    uint8_t range_val = (uint8_t)RANGE;
    uint32_t nb_val = (uint32_t)num_blocks;

    fwrite(&ns, 4, 1, fout);
    fwrite(&range_val, 1, 1, fout);
    fwrite(&mode, 1, 1, fout);
    fwrite(&nb_val, 4, 1, fout);

    if (mode == 1) {
        for (uint32_t b = 0; b < num_blocks; b++) {
            fwrite(&block_metas[b].cfg0, 1, 1, fout);
            fwrite(&block_metas[b].cfg1, 1, 1, fout);
            fwrite(&block_metas[b].blk_bytes, 4, 1, fout);
            fwrite(global_bitstream_buffer + block_metas[b].offset, 1,
                   block_metas[b].blk_bytes, fout);
        }
    } else {
        memset(raw_buffer, 0, raw_payload_bytes);
        for (int i = 0; i < symbol_count; i++) {
            if (symbols_buffer[i]) {
                raw_buffer[i / 8] |= (1 << (7 - (i % 8)));
            }
        }
        fwrite(raw_buffer, 1, raw_payload_bytes, fout);
    }
    fclose(fout);

    double p0 = (double)count0 / symbol_count, p1 = 1.0 - p0;
    double h = 0.0;
    if (p0 > 0.0) {
        h -= p0 * log2(p0);
    }
    if (p1 > 0.0) {
        h -= p1 * log2(p1);
    }
    double taxa =
        (1.0 - (double)(final_total_bytes * 8) / symbol_count) * 100.0;

    printf(
        "\n==================================================================="
        "=====\n");
    printf(
        "  tANS 1D POR BLOCOS INDEPENDENTES  |  RANGE=%d  |  BLOCK_SIZE=%d\n",
        RANGE, BLOCK_SIZE);
    printf(
        "====================================================================="
        "===\n");
    printf("Arquivo           : %s\n", filename);
    printf("Símbolos lidos    : %d (0s: %d, 1s: %d)\n", symbol_count, count0,
           count1);
    printf("Blocos            : %u (tamanho fixo %d símbolos)\n", num_blocks,
           BLOCK_SIZE);
    printf("Modo selecionado  : %s\n", (mode == 1)
                                           ? "1D-tANS (Blocos Independentes)"
                                           : "RAW (Fallback sem perda)");
    printf("Entropia H (ord0) : %.6f bits/símbolo\n", h);
    printf("Total transmitido : %zu bytes  (%zu bits)\n", final_total_bytes,
           final_total_bytes * 8);
    printf("Taxa de compressão: %.2f%%\n", taxa);
    {
        /* Detalhamento em bits (usado pelo relatório do Bit_Planes.py) */
        long long ov_bits, est_bits = 0, pad_bits, bitstream_bits;
        if (mode == 1) {
            long long used = 0, alloc = 0;
            for (uint32_t b = 0; b < num_blocks; b++) {
                used += block_metas[b].bits_used;
                alloc += (long long)block_metas[b].blk_bytes * 8;
            }
            ov_bits = (10 + (long long)num_blocks * 6) * 8;
            est_bits = (long long)num_blocks * (FLUSH_BITS + 1);
            pad_bits = alloc - used;
            bitstream_bits = used - est_bits;
        } else {
            ov_bits = 10 * 8;
            pad_bits = (long long)raw_payload_bytes * 8 - symbol_count;
            bitstream_bits = symbol_count;
        }
        printf("Blocos tANS       : %u\n", mode == 1 ? num_blocks : 0);
        printf("Overhead (bits)   : %lld\n", ov_bits);
        printf("Preenchimento (bits): %lld\n", pad_bits);
        printf("Estado (bits)     : %lld\n", est_bits);
        printf("Bitstream (bits)  : %lld\n", bitstream_bits);
        printf("Comprimido (bits) : %zu\n", final_total_bytes * 8);
    }
    printf("Arquivo gerado    : %s\n", output_filename);
    printf(
        "====================================================================="
        "===\n");
}

/*
 MAIN
 */

int main(int argc, char *argv[]) {

    printf("tANS Contextual 1D Encoder\n");

    if (argc < 2) {

        fprintf(stderr, "Uso: %s <arquivo.txt>\n", argv[0]);

        return 1;
    }

    for (int i = 1; i < argc; i++) {

        process_file(argv[i]);
    }

    printf("\nProcessamento concluido.\n");

    return 0;
}
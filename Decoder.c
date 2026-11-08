/*
 tANS STATIC DECODER
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "tans_tables.h"

/* Buffer estático para símbolos decodificados */
#define MAX_DECODED_SYMBOLS 12000000

#define BITSTREAM_CAPACITY 2000000

/* Tamanho de bloco — sincronizado com Encoder */
#ifndef BLOCK_SIZE
#define BLOCK_SIZE 10000
#endif

/*
 DEBUG
 */

#define DEBUG 1

#if DEBUG
#define DBG_PRINTF(...) printf(__VA_ARGS__)
#else
#define DBG_PRINTF(...)
#endif

/*
 ESTRUTURAS
 */

typedef struct {
    uint32_t state;
} AnsState;

/*
 Para cada estado de chegada (state_idx) guardamos TODOS os estados de
 origem possíveis. Cada candidato emitiu 'nbits' bits na codificação,
 que são os 'nbits' bits menos significativos do estado de origem.
 Os códigos são livres de prefixo, então basta ler bit a bit até
 coincidir com algum candidato.
*/
#define MAX_CAND (2 * RANGE)

typedef struct {
    int ncand;
    uint8_t prev[MAX_CAND];  /* índice do estado de origem (state - RANGE) */
    uint8_t nbits[MAX_CAND]; /* bits emitidos nessa transição */
    uint8_t sym[MAX_CAND];   /* símbolo codificado nessa transição */
} DecodeEntry;

typedef struct {
    uint8_t *buffer;
    int total_bits;
    int current_bit;
} BitstreamReader;

/*
 GLOBAIS
 */

static DecodeEntry g_rlt[2][RANGE]; /* [ctx_id][state_idx] */
static uint8_t bitstream_buffer[BITSTREAM_CAPACITY];
static int decoded_symbols[MAX_DECODED_SYMBOLS];

/*
 BUILD RLT
 */

void build_rlt(int ctx_id, int cfg) {

#if RANGE == 10
    const uint8_t(*at)[10] = a_range10;
    const uint8_t(*an)[10] = a_nbits_range10;
    const uint8_t(*bt)[10] = b_range10;
    const uint8_t(*bn)[10] = b_nbits_range10;
#elif RANGE == 9
    const uint8_t(*at)[9] = a_range9;
    const uint8_t(*an)[9] = a_nbits_range9;
    const uint8_t(*bt)[9] = b_range9;
    const uint8_t(*bn)[9] = b_nbits_range9;
#elif RANGE == 8
    const uint8_t(*at)[8] = a_range8;
    const uint8_t(*an)[8] = a_nbits_range8;
    const uint8_t(*bt)[8] = b_range8;
    const uint8_t(*bn)[8] = b_nbits_range8;
#elif RANGE == 6
    const uint8_t(*at)[6] = a_range6;
    const uint8_t(*an)[6] = a_nbits_range6;
    const uint8_t(*bt)[6] = b_range6;
    const uint8_t(*bn)[6] = b_nbits_range6;
#elif RANGE == 4
    const uint8_t(*at)[4] = a_range4;
    const uint8_t(*an)[4] = a_nbits_range4;
    const uint8_t(*bt)[4] = b_range4;
    const uint8_t(*bn)[4] = b_nbits_range4;
#else
    const uint8_t(*at)[2] = a_range2;
    const uint8_t(*an)[2] = a_nbits_range2;
    const uint8_t(*bt)[2] = b_range2;
    const uint8_t(*bn)[2] = b_nbits_range2;
#endif

    for (int i = 0; i < RANGE; i++) {
        g_rlt[ctx_id][i].ncand = 0;
    }

    for (int prev_idx = 0; prev_idx < RANGE; prev_idx++) {
        /* símbolo 0 */
        DecodeEntry *e = &g_rlt[ctx_id][at[cfg][prev_idx] - RANGE];
        e->prev[e->ncand] = (uint8_t)prev_idx;
        e->nbits[e->ncand] = an[cfg][prev_idx];
        e->sym[e->ncand] = 0;
        e->ncand++;

        /* símbolo 1 */
        e = &g_rlt[ctx_id][bt[cfg][prev_idx] - RANGE];
        e->prev[e->ncand] = (uint8_t)prev_idx;
        e->nbits[e->ncand] = bn[cfg][prev_idx];
        e->sym[e->ncand] = 1;
        e->ncand++;
    }
}

/*
 BITSTREAM
 */

void bitstream_reader_init(BitstreamReader *reader, uint8_t *buffer,
                           int total_bits) {
    reader->buffer = buffer;
    reader->total_bits = total_bits;
    reader->current_bit = total_bits - 1;
}

uint32_t bitstream_read_bits_lsb(BitstreamReader *reader, int nbits) {
    uint32_t result = 0;
    for (int i = 0; i < nbits; i++) {
        if (reader->current_bit < 0) {
            return 0;
        }
        int bit_index = reader->current_bit;
        uint8_t bit =
            (reader->buffer[bit_index / 8] >> (7 - (bit_index % 8))) & 1;
        if (bit) {
            result |= (1U << i);
        }
        reader->current_bit--;
    }
    return result;
}

uint32_t bitstream_read_bits_msb(BitstreamReader *reader, int nbits) {
    uint32_t result = 0;
    for (int i = 0; i < nbits; i++) {
        if (reader->current_bit < 0) {
            return 0;
        }
        int bit_index = reader->current_bit;
        uint8_t bit =
            (reader->buffer[bit_index / 8] >> (7 - (bit_index % 8))) & 1;
        result = (result << 1) | bit;
        reader->current_bit--;
    }
    return result;
}

/*
 DECODE
*/

int ans_decode_symbol_ctx(int ctx_id, AnsState *state,
                          BitstreamReader *reader) {
    int idx = state->state - RANGE;
    if (idx < 0 || idx >= RANGE) {
        fprintf(stderr, "Estado invalido: %u\n", state->state);
        return -1;
    }
    DecodeEntry *e = &g_rlt[ctx_id][idx];

    /* Lê bit a bit (MSB primeiro) até casar com os 'k' bits baixos de algum
   * estado de origem que emitiu exatamente 'k' bits. */
    uint32_t r = 0;
    for (int k = 0; k <= 8; k++) {
        for (int c = 0; c < e->ncand; c++) {
            uint32_t prev_state = RANGE + e->prev[c];
            uint32_t mask = (1u << k) - 1u;
            if (e->nbits[c] == k && (prev_state & mask) == r) {
                state->state = prev_state;
                return e->sym[c];
            }
        }
        r = (r << 1) | bitstream_read_bits_msb(reader, 1);
    }
    return -1;
}

/*
 PROCESS FILE
 */

void decode_file(const char *input_file, const char *output_file) {
    FILE *f = fopen(input_file, "rb");
    if (!f) {
        perror("fopen entrada");
        return;
    }

    /* Header global: 10B -> [num_symbols (4B)] [RANGE (1B)] [mode (1B)]
   * [num_blocks (4B)] */
    uint32_t num_symbols = 0, num_blocks = 0;
    uint8_t file_range = 0, mode = 0;

    if (fread(&num_symbols, 4, 1, f) != 1 || fread(&file_range, 1, 1, f) != 1 ||
        fread(&mode, 1, 1, f) != 1 || fread(&num_blocks, 4, 1, f) != 1) {
        fprintf(stderr,
                "ERRO: cabeçalho global inválido ou arquivo truncado.\n");
        fclose(f);
        return;
    }

    if (num_symbols == 0 || num_symbols > MAX_DECODED_SYMBOLS) {
        fprintf(stderr, "ERRO: número de símbolos inválido (%u).\n",
                num_symbols);
        fclose(f);
        return;
    }

    if (mode == 1 && file_range != RANGE) {
        fprintf(
            stderr,
            "ERRO: Arquivo codificado com RANGE=%u, mas decoder compilado para "
            "RANGE=%d.\n"
            "Por favor, recompile o decoder com: gcc -DRANGE=%u Decoder.c -o "
            "decoder\n",
            file_range, RANGE, file_range);
        fclose(f);
        return;
    }

    FILE *out = fopen(output_file, "w");
    if (!out) {
        perror("fopen saida");
        fclose(f);
        return;
    }

    if (mode == 1) {
        /* Modo 1D Contextual tANS por Blocos Independentes */
        for (uint32_t b = 0; b < num_blocks; b++) {
            int bstart = b * BLOCK_SIZE;
            int bend = bstart + BLOCK_SIZE;
            if (bend > (int)num_symbols) {
                bend = (int)num_symbols;
            }
            int blk_syms = bend - bstart;

            uint8_t cfg0 = 0, cfg1 = 0;
            uint32_t blk_bytes = 0;

            if (fread(&cfg0, 1, 1, f) != 1 || fread(&cfg1, 1, 1, f) != 1 ||
                fread(&blk_bytes, 4, 1, f) != 1) {
                fprintf(stderr, "ERRO: falha ao ler cabeçalho do bloco %u.\n",
                        b);
                fclose(f);
                fclose(out);
                return;
            }

            if (blk_bytes > BITSTREAM_CAPACITY) {
                fprintf(
                    stderr,
                    "ERRO: tamanho do bloco %u excede capacidade (%u bytes).\n",
                    b, blk_bytes);
                fclose(f);
                fclose(out);
                return;
            }

            size_t bytes_read = fread(bitstream_buffer, 1, blk_bytes, f);
            if (bytes_read != blk_bytes) {
                fprintf(stderr,
                        "ERRO: bloco %u truncado (%zu de %u bytes lidos).\n", b,
                        bytes_read, blk_bytes);
                fclose(f);
                fclose(out);
                return;
            }

            build_rlt(0, cfg0);
            build_rlt(1, cfg1);

            int total_bits = (int)blk_bytes * 8;
            while (total_bits > FLUSH_BITS + 1) {
                int bi = total_bits - 1;
                if ((bitstream_buffer[bi / 8] >> (7 - (bi % 8))) & 1) {
                    break;
                }
                total_bits--;
            }

            BitstreamReader reader;
            bitstream_reader_init(&reader, bitstream_buffer, total_bits);
            reader.current_bit--; /* pula stop bit */

            uint32_t off = bitstream_read_bits_lsb(&reader, FLUSH_BITS);
            AnsState state;
            state.state = RANGE + off;

            /* Decodifica do fim para o início com contexto lookahead 1D independente
       */
            for (int i = blk_syms - 1; i >= 0; i--) {
                int nxt =
                    (i + 1 < blk_syms) ? decoded_symbols[bstart + i + 1] : 0;
                int sym = ans_decode_symbol_ctx(nxt, &state, &reader);
                if (sym == -1) {
                    fprintf(
                        stderr,
                        "ERRO: decodificação falhou no bloco %u, símbolo %d.\n",
                        b, i);
                    fclose(f);
                    fclose(out);
                    return;
                }
                decoded_symbols[bstart + i] = sym;
            }
        }
    } else {
        /* Modo RAW */
        size_t raw_payload_bytes = (num_symbols + 7) / 8;
        size_t bytes_read = fread(bitstream_buffer, 1, raw_payload_bytes, f);
        if (bytes_read != raw_payload_bytes) {
            fprintf(stderr,
                    "ERRO: payload RAW truncado (%zu de %zu bytes lidos).\n",
                    bytes_read, raw_payload_bytes);
            fclose(f);
            fclose(out);
            return;
        }
        for (uint32_t i = 0; i < num_symbols; i++) {
            decoded_symbols[i] = (bitstream_buffer[i / 8] >> (7 - (i % 8))) & 1;
        }
    }

    fclose(f);

    /* Grava símbolos decodificados */
    for (uint32_t i = 0; i < num_symbols; i++) {
        fprintf(out, "%d", decoded_symbols[i]);
        if (i + 1 < num_symbols) {
            fprintf(out, " ");
        }
    }
    fclose(out);

    printf("Arquivo decodificado com sucesso: %s (%u simbolos, modo %s)\n",
           output_file, num_symbols, (mode == 1 ? "1D-tANS Blocos" : "RAW"));
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Uso: %s <arquivo_encoded.bin> <arquivo_decoded.txt>\n",
                argv[0]);
        return 1;
    }
    decode_file(argv[1], argv[2]);
    return 0;
}
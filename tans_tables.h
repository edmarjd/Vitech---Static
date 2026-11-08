/* =============================================================================
 * tans_tables.h  -  Tabelas pré-computadas para codificação tANS estática
 *
 * ARQUIVO GERADO por ANS-Streaming Encoder.py (--gerar-tabelas) - não editar à mão.
 *
 * Alfabeto binário: símbolo 0 e símbolo 1
 * RANGE = 10  →  espaço de estados [10, 19]  (índices 0..9)
 * FLUSH_BITS = 4  (ceil(log2(RANGE)) bits para salvar o estado final)
 *
 * Configurações disponíveis (RANGE == 10):
 *   cfg 0 : P(0) = 9/10 = 90%,  P(1) = 1/10 = 10%
 *   cfg 1 : P(0) = 1/10 = 10%,  P(1) = 9/10 = 90%
 *
 * Como as tabelas foram geradas (pelo rANS)
 * ─────────────────────────────────────────
 * Cada entrada é o encoder rANS streaming do projeto (run_all.py) aplicado a
 * um estado x ∈ [RANGE, 2·RANGE-1] e a um símbolo s, com M = RANGE,
 * F(0) = f0, F(1) = M - f0, C(0) = 0, C(1) = f0:
 *   1. Renormalização: enquanto x >= 2·F(s), emite x & 1 e faz x >>= 1.
 *      Os bits saem LSB primeiro; o valor guardado é o 1º bit emitido como
 *      bit mais alto (o writer em C grava o valor MSB primeiro).
 *   2. Equação (7): novo estado = (x / F(s))·M + C(s) + (x mod F(s)).
 * Resultado: cada símbolo ocupa um bloco contíguo de estados (layout do
 * tutorial LASCAS 2025). Bits emitidos usam 0xFF (EMPTY) quando nenhum bit sai.
 *
 * Convenção de nomes:
 *   a_*  →  símbolo 0     b_*  →  símbolo 1
 *   *_table      novo estado após a transição
 *   *_bitstream  bits emitidos (0xFF = nenhum bit)
 *   *_nbits      número de bits emitidos
 * ============================================================================= */

#ifndef TANS_TABLES_H
#define TANS_TABLES_H

#include <stdint.h>

#define RANGE      10    /* Tamanho do espaço de estados L: estados em [L, 2L-1] */
#define FLUSH_BITS  4    /* Bits para armazenar o estado final: ceil(log2(RANGE)) */
#define EMPTY      0xFF  /* Sentinela: nenhum bit emitido nesta transição */

/* Novo estado ao encodar símbolo 0 */
static const uint8_t a_range10[2][10] = {
    {11, 12, 13, 14, 15, 16, 17, 18, 10, 10}, /* cfg 0: P(0)=9/10 */
    {10, 10, 10, 10, 10, 10, 10, 10, 10, 10}, /* cfg 1: P(0)=1/10 */
};

/* Bits emitidos ao encodar símbolo 0 (0xFF = nenhum bit) */
static const uint8_t a_bitstream_range10[2][10] = {
    {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x01}, /* cfg 0: P(0)=9/10 */
    {0x02, 0x06, 0x01, 0x05, 0x03, 0x07, 0x00, 0x08, 0x04, 0x0C}, /* cfg 1: P(0)=1/10 */
};

/* Número de bits emitidos ao encodar símbolo 0 */
static const uint8_t a_nbits_range10[2][10] = {
    {0, 0, 0, 0, 0, 0, 0, 0, 1, 1}, /* cfg 0: P(0)=9/10 */
    {3, 3, 3, 3, 3, 3, 4, 4, 4, 4}, /* cfg 1: P(0)=1/10 */
};

/* Novo estado ao encodar símbolo 1 */
static const uint8_t b_range10[2][10] = {
    {19, 19, 19, 19, 19, 19, 19, 19, 19, 19}, /* cfg 0: P(0)=9/10 */
    {12, 13, 14, 15, 16, 17, 18, 19, 11, 11}, /* cfg 1: P(0)=1/10 */
};

/* Bits emitidos ao encodar símbolo 1 (0xFF = nenhum bit) */
static const uint8_t b_bitstream_range10[2][10] = {
    {0x02, 0x06, 0x01, 0x05, 0x03, 0x07, 0x00, 0x08, 0x04, 0x0C}, /* cfg 0: P(0)=9/10 */
    {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x01}, /* cfg 1: P(0)=1/10 */
};

/* Número de bits emitidos ao encodar símbolo 1 */
static const uint8_t b_nbits_range10[2][10] = {
    {3, 3, 3, 3, 3, 3, 4, 4, 4, 4}, /* cfg 0: P(0)=9/10 */
    {0, 0, 0, 0, 0, 0, 0, 0, 1, 1}, /* cfg 1: P(0)=1/10 */
};

/* Frequência do símbolo 0 por configuração (usada em select_cfg) */
static const int freq_a_range10[2] = {9, 1};

#endif /* TANS_TABLES_H */

import cv2
import numpy as np
import matplotlib

matplotlib.use('Agg')  # só salva a figura, não abre janela
import matplotlib.pyplot as plt
import subprocess
import os


def bit_plane_slicing(image_path):
    # Carrega a imagem em escala de cinza
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    # Verifica se a imagem foi carregada corretamente
    if img is None:
        print("Erro ao carregar a imagem.")
        return

    planes_visual = []  # Lista para armazenar os planos para visualização (0 ou 255)
    planes_binary = {}  # Dicionário para armazenar os planos binários (0 ou 1)

    # Itera pelos 8 planos de bits (do bit 0 ao bit 7)
    for i in range(8):
        # Cria uma máscara com o valor 2^i (isola o bit i de cada pixel)
        plane_mask = np.full(img.shape, 2**i, np.uint8)

        # Aplica AND bit a bit entre a imagem e a máscara, extraindo apenas o bit i
        res = cv2.bitwise_and(img, plane_mask)

        # Converte o resultado para binário (0 ou 1)
        binary_matrix = (res > 0).astype(np.uint8)

        # Salva o plano binário no dicionário
        planes_binary[i] = binary_matrix

        # Salva o plano visual (multiplica por 255 para exibir como branco/preto)
        planes_visual.append(binary_matrix * 255)

    # Salva cada plano de bit como arquivo de texto
    for bit in range(8):
        filename = f'plano_bit_{bit}.txt'
        # Flatten para garantir que salve como sequência contínua de 0s e 1s
        np.savetxt(filename, planes_binary[bit].flatten(), fmt='%d', delimiter='')
        print(f"Plano {bit} salvo com sucesso em: {filename}")

    # Cria uma figura com subplots para exibir os 8 planos de bits
    plt.figure(figsize=(12, 8))
    for i in range(8):
        plt.subplot(2, 4, i + 1)  # Organiza em grade 2x4
        plt.imshow(planes_visual[i], cmap='gray')
        plt.title(f'Plano de Bit {i}')
        plt.axis('off')  # Remove os eixos para visualização limpa

    plt.tight_layout()
    # Salva a figura com os planos de bits como imagem PNG
    plt.savefig('resultado_planos_bits.png', dpi=300)
    print("Gráfico dos planos de bits salvo com sucesso como 'resultado_planos_bits.png'!")


def testar_tans(encoder="./encoder", decoder="./decoder", detalhe=False, nome_img="imagem"):
    """Roda encoder/decoder em C (tANS) em cada plano_bit_N.txt, confere a
    decodificação e imprime um relatório em tabela (uma coluna por plano)."""
    import time
    import re

    for exe in (encoder, decoder):
        if not os.path.exists(exe):
            print(f"\n'{exe}' não encontrado. Compile antes:")
            print("  gcc -O2 Encoder_Ans.c -o encoder -lm")
            print("  gcc -O2 Decoder.c -o decoder")
            return

    def campo(texto, prefixo):
        for linha in texto.splitlines():
            if linha.startswith(prefixo):
                return linha.split(":", 1)[1].strip()
        return ""

    def inteiro(texto, prefixo):
        m = re.match(r"-?\d+", campo(texto, prefixo))
        return int(m.group()) if m else 0

    dados, tudo_ok = [], True
    for bit in range(8):
        txt = f"plano_bit_{bit}.txt"
        enc = f"plano_bit_{bit}_encoded.bin"
        out = f"saida_{bit}.txt"

        cmd = [encoder, txt]
        t0 = time.perf_counter()
        r = subprocess.run(cmd, check=True, capture_output=True, text=True)
        t_enc = time.perf_counter() - t0
        if "RANGE=" not in r.stdout:
            print(f"\nERRO no encoder (plano {bit}):\n{r.stdout}\n{r.stderr}")
            return

        t0 = time.perf_counter()
        d = subprocess.run([decoder, enc, out], check=True, capture_output=True, text=True)
        t_dec = time.perf_counter() - t0

        if detalhe:
            print("\n" + "#" * 70 + f"\n#  PLANO DE BIT {bit}\n" + "#" * 70)
            print(r.stdout.strip())
            print("\n[DECODER]\n" + d.stdout.strip())

        original = open(txt).read().split()
        decodif = open(out).read().split()
        ok = original == decodif
        tudo_ok &= ok

        modo_raw = "RAW" in campo(r.stdout, "Modo selecionado")
        orig = len(original)
        comp = inteiro(r.stdout, "Comprimido (bits)")
        dados.append(
            {
                "orig": orig,
                "blocos": inteiro(r.stdout, "Blocos tANS"),
                "overhead": inteiro(r.stdout, "Overhead (bits)"),
                "pad": inteiro(r.stdout, "Preenchimento (bits)"),
                "estado": inteiro(r.stdout, "Estado (bits)"),
                "bitstream": inteiro(r.stdout, "Bitstream (bits)"),
                "comp": comp,
                "ganho": orig - comp,
                "taxa": 100 * (1 - comp / orig),
                "tabela": (
                    "RAW" if modo_raw else f"L={re.search(r'RANGE=(\d+)', r.stdout).group(1)}"
                ),
                "bs": int(re.search(r"BLOCK_SIZE=(\d+)", r.stdout).group(1)),
                "t_enc": t_enc * 1000,
                "t_dec": t_dec * 1000,
                "ok": "OK" if ok else "ERRO",
            }
        )

    # coluna TOTAL (soma dos 8 planos)
    tot = {
        k: sum(x[k] for x in dados)
        for k in (
            "orig",
            "blocos",
            "overhead",
            "pad",
            "estado",
            "bitstream",
            "comp",
            "ganho",
            "t_enc",
            "t_dec",
        )
    }
    tot["taxa"] = 100 * (1 - tot["comp"] / tot["orig"])
    tot["tabela"] = "-"
    tot["ok"] = "OK" if tudo_ok else "ERRO"
    dados.append(tot)

    bs = dados[0]["bs"]

    inteiro_f = lambda k: [f"{x[k]:,}".replace(",", ".") for x in dados]
    pct_f = lambda k: [f"{x[k]:.2f}%".replace(".", ",") for x in dados]
    ms_f = lambda k: [f"{x[k]:.1f}".replace(".", ",") for x in dados]
    linhas = [
        ("TAMANHO ORIGINAL (BITS)", inteiro_f("orig")),
        ("TABELA (RANGE)", [x["tabela"] for x in dados]),
        ("TAMANHO TOTAL DE BLOCOS", inteiro_f("blocos")),
        ("OVERHEAD (BITS)", inteiro_f("overhead")),
        ("BITS DE PREENCHIMENTO", inteiro_f("pad")),
        ("ESTADO (BITS)", inteiro_f("estado")),
        ("BITSTREAM", inteiro_f("bitstream")),
        ("COMPRIMIDO GLOBAL", inteiro_f("comp")),
        ("GANHO TOTAL (BITS)", inteiro_f("ganho")),
        ("TAXA DE COMPRESSAO", pct_f("taxa")),
        ("TEMPO ENCODER (ms)", ms_f("t_enc")),
        ("TEMPO DECODER (ms)", ms_f("t_dec")),
        ("VERIFICACAO LOSSLESS", [x["ok"] for x in dados]),
    ]
    cab = [f"PLANO {i}" for i in range(8)] + ["TOTAL"]
    w0 = max(len(n) for n, _ in linhas) + 1
    wc = max(11, max(len(v) for _, vs in linhas for v in vs) + 1)
    larg = w0 + wc * len(cab)

    titulo = f"PLANOS DE BITS BLOCO({bs})  -  {nome_img}"
    print("\n" + "=" * larg)
    print(titulo.center(larg))
    print("=" * larg)
    print(" " * w0 + "".join(c.rjust(wc) for c in cab))
    print("-" * larg)
    for nome, vals in linhas:
        print(nome.ljust(w0) + "".join(v.rjust(wc) for v in vals))
        if nome in ("TAMANHO ORIGINAL (BITS)", "COMPRIMIDO GLOBAL", "TAXA DE COMPRESSAO"):
            print("-" * larg)
    print("=" * larg)


if __name__ == "__main__":
    import sys
    import os

    target = "foto.png"  # Imagem padrão

    # Verifica se foi passado um argumento pela linha de comando
    if len(sys.argv) > 1:
        target = sys.argv[1]
    elif os.path.exists("foto.png"):  # Usa foto.png se existir
        target = "foto.png"
    elif os.path.exists("foto.jpg"):  # Tenta foto.jpg como alternativa
        target = "foto.jpg"

    bit_plane_slicing(target)
    # Opção: --detalhe mostra o log completo de cada plano
    testar_tans(detalhe="--detalhe" in sys.argv[2:], nome_img=target)
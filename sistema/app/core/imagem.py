"""Ajuste automático das fotos dos produtos (igual às vitrines do Mercado Livre e da Shopee).

Toda foto, venha da câmera do celular ou do computador, vira um QUADRADO de 1000 x 1000
com fundo branco: o produto aparece inteiro (sem cortar), já de pé (o celular às vezes
manda a foto "deitada") e leve (JPEG), para a vitrine abrir rápido no celular.
"""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

LADO = 1000          # tamanho final (quadrado), em pixels
MAX_ENTRADA = 25 * 1024 * 1024  # fotos maiores que 25 MB nem são abertas


class FotoInvalida(ValueError):
    pass


def ajustar(conteudo: bytes) -> bytes:
    """Recebe a foto como veio e devolve o quadrado pronto para a vitrine (JPEG)."""
    if not conteudo:
        raise FotoInvalida("A foto veio vazia.")
    if len(conteudo) > MAX_ENTRADA:
        raise FotoInvalida("A foto é grande demais.")
    try:
        foto = Image.open(BytesIO(conteudo))
        foto.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise FotoInvalida("Esse arquivo não é uma foto.") from e

    foto = ImageOps.exif_transpose(foto)  # deixa de pé, como a pessoa viu na tela
    if foto.mode in ("RGBA", "LA", "P"):  # fundo transparente (PNG) vira branco
        foto = foto.convert("RGBA")
        branco = Image.new("RGBA", foto.size, "white")
        foto = Image.alpha_composite(branco, foto)
    foto = foto.convert("RGB")

    foto.thumbnail((LADO, LADO), Image.Resampling.LANCZOS)  # cabe inteira no quadrado
    quadro = Image.new("RGB", (LADO, LADO), "white")
    quadro.paste(foto, ((LADO - foto.width) // 2, (LADO - foto.height) // 2))

    saida = BytesIO()
    quadro.save(saida, "JPEG", quality=85, optimize=True, progressive=True)
    return saida.getvalue()

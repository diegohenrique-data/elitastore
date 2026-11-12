"""Ajuste automático das fotos: toda foto vira um quadrado de 1000 x 1000, de pé, com fundo branco."""

from io import BytesIO

import pytest
from PIL import Image

from app.core import imagem


def _foto(largura, altura, cor="red", formato="JPEG", modo="RGB", **extra) -> bytes:
    saida = BytesIO()
    Image.new(modo, (largura, altura), cor).save(saida, formato, **extra)
    return saida.getvalue()


def _abrir(conteudo):
    return Image.open(BytesIO(conteudo))


def test_foto_deitada_vira_quadrado_sem_cortar():
    pronta = _abrir(imagem.ajustar(_foto(4000, 2000)))
    assert pronta.format == "JPEG" and pronta.size == (1000, 1000)
    assert pronta.getpixel((500, 10))[0] > 240 and pronta.getpixel((500, 10))[1] > 240  # faixa branca em cima
    assert pronta.getpixel((500, 500))[0] > 200 and pronta.getpixel((500, 500))[1] < 60  # o produto inteiro no meio


def test_foto_pequena_e_png_transparente():
    assert _abrir(imagem.ajustar(_foto(300, 500))).size == (1000, 1000)
    pronta = _abrir(imagem.ajustar(_foto(400, 400, cor=(0, 0, 0, 0), formato="PNG", modo="RGBA")))
    assert pronta.getpixel((500, 500)) == (255, 255, 255)  # transparente vira branco


def test_foto_do_celular_fica_de_pe():
    exif = Image.Exif()
    exif[0x0112] = 6  # o celular salvou "deitada" e mandou girar 90°
    pronta = _abrir(imagem.ajustar(_foto(1600, 800, exif=exif)))
    assert pronta.getpixel((500, 20))[1] < 60  # agora em pé: ocupa a altura toda
    assert pronta.getpixel((20, 500))[1] > 240  # e sobra branco dos lados


def test_arquivo_que_nao_e_foto():
    with pytest.raises(imagem.FotoInvalida):
        imagem.ajustar(b"isto nao e uma foto")
    with pytest.raises(imagem.FotoInvalida):
        imagem.ajustar(b"")

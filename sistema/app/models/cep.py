"""Endereço pelo CEP (ViaCEP: gratuito e sem chave; a API oficial dos Correios exige contrato)."""

import json
import re
import urllib.error
import urllib.request

URL = "https://viacep.com.br/ws/{}/json/"


class ForaDoAr(Exception):
    """A busca de CEP não respondeu (sem internet ou serviço fora do ar)."""


def limpar(cep: str) -> str:
    return re.sub(r"\D", "", cep or "")


def com_traco(cep: str) -> str:
    return f"{cep[:5]}-{cep[5:]}"


def buscar(cep: str) -> dict | None:
    """Os dados do CEP, ou None se ele não existe."""
    digitos = limpar(cep)
    if len(digitos) != 8:
        return None
    try:
        with urllib.request.urlopen(URL.format(digitos), timeout=6) as resposta:
            dados = json.load(resposta)
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return None
        raise ForaDoAr from e
    except (OSError, ValueError) as e:
        raise ForaDoAr from e
    return None if dados.get("erro") else dados


def rua_e_cidade(dados: dict) -> str:
    """'Praça da Sé - Sé, São Paulo - SP'. Cidade de CEP único vem sem rua e sem bairro."""
    local = " - ".join(p for p in (dados.get("logradouro"), dados.get("bairro")) if p)
    cidade = " - ".join(p for p in (dados.get("localidade"), dados.get("uf")) if p)
    return ", ".join(p for p in (local, cidade) if p)


def montar(dados: dict, numero: str) -> str:
    """O endereço completo que vai para a ficha da pessoa."""
    return f"{rua_e_cidade(dados)}, nº {numero.strip()}, CEP {com_traco(limpar(dados.get('cep', '')))}"


def resolver(cep: str, numero: str, sem_cep: bool, endereco: str) -> tuple[dict, str | None]:
    """Campos de endereço da pessoa, e o erro para mostrar (None se está tudo certo)."""
    if sem_cep:
        return {"cep": "", "numero": "", "endereco": endereco.strip()}, None
    digitos = limpar(cep)
    campos = {"cep": digitos, "numero": numero.strip(), "endereco": ""}
    if len(digitos) != 8:
        return campos, "Escreva o CEP com 8 números. Se a pessoa não tem CEP, marque a opção."
    if not campos["numero"]:
        return campos, "Falta o número da casa. Se não tiver, escreva S/N."
    try:
        dados = buscar(digitos)
    except ForaDoAr:
        return campos, "Não consegui buscar o CEP agora. Tente de novo ou marque que a pessoa não tem CEP."
    if not dados:
        return campos, "Não achei esse CEP. Confira os números ou marque que a pessoa não tem CEP."
    campos["endereco"] = montar(dados, campos["numero"])
    return campos, None

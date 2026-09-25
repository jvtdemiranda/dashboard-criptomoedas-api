"""
Busca preços de criptomoedas na API pública da CoinGecko e salva um
snapshot em data/atual.json, além de acrescentar uma linha ao histórico
de execuções (data/historico_execucoes.csv) — a prova de que o pipeline
roda de verdade e periodicamente, não é uma foto única.

Primeira etapa do pipeline:
1. buscar_dados.py         -> chama a API, gera data/atual.json (este script)
2. gerar_dashboard_html.py -> monta public/index.html a partir do snapshot
"""

import csv
import json
import os
import time
from datetime import datetime, timezone

import requests

API_URL = "https://api.coingecko.com/api/v3/coins/markets"
MOEDAS = 15  # top N por market cap
MOEDA_BASE = "brl"
TIMEOUT_SEGUNDOS = 20
MAX_TENTATIVAS = 3
HISTORICO_MAX_LINHAS = 500  # bounded: ~500 execuções, não cresce pra sempre


def caminhos():
    pasta_raiz = os.path.join(os.path.dirname(__file__), "..")
    pasta_data = os.path.join(pasta_raiz, "data")
    os.makedirs(pasta_data, exist_ok=True)
    return (
        os.path.join(pasta_data, "atual.json"),
        os.path.join(pasta_data, "historico_execucoes.csv"),
    )


def buscar_moedas() -> list[dict]:
    params = {
        "vs_currency": MOEDA_BASE,
        "order": "market_cap_desc",
        "per_page": MOEDAS,
        "page": 1,
        "sparkline": "true",
        "price_change_percentage": "24h,7d",
    }
    # A API pública da CoinGecko tem limite de taxa (free tier) — uma
    # tentativa que falhe com 429 vale a pena repetir antes de desistir,
    # já que o pipeline roda sozinho (sem alguém pra simplesmente rodar
    # de novo na hora). Repetir sem espera não ajuda contra rate limit
    # (a janela de limite dura muito mais que o tempo entre tentativas
    # instantâneas), por isso o backoff exponencial entre elas.
    ultimo_erro = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=TIMEOUT_SEGUNDOS,
                                 headers={"User-Agent": "portfolio-dashboard-cripto/1.0"})
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            ultimo_erro = e
            print(f"Tentativa {tentativa}/{MAX_TENTATIVAS} falhou: {e}")
            if tentativa < MAX_TENTATIVAS:
                espera = 2 ** tentativa  # 2s, 4s, ...
                print(f"Aguardando {espera}s antes de tentar de novo...")
                time.sleep(espera)
    raise RuntimeError(f"Não foi possível buscar dados da CoinGecko após {MAX_TENTATIVAS} tentativas") from ultimo_erro


def normalizar(moedas_bruto: list[dict]) -> list[dict]:
    moedas = []
    for m in moedas_bruto:
        sparkline = (m.get("sparkline_in_7d") or {}).get("price") or []
        moedas.append({
            "id": m["id"],
            "simbolo": m["symbol"].upper(),
            "nome": m["name"],
            "preco": m["current_price"],
            "variacao_24h_pct": m.get("price_change_percentage_24h"),
            "variacao_7d_pct": m.get("price_change_percentage_7d_in_currency"),
            "market_cap": m["market_cap"],
            "volume_24h": m["total_volume"],
            "sparkline_7d": sparkline,
        })
    return moedas


def salvar_snapshot(caminho_json: str, moedas: list[dict], buscado_em: str) -> None:
    payload = {"buscado_em": buscado_em, "moeda_base": MOEDA_BASE, "moedas": moedas}
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def registrar_execucao(caminho_csv: str, buscado_em: str, moedas: list[dict]) -> None:
    """Acrescenta uma linha ao log de execuções (bitcoin como referência de preço)."""
    bitcoin = next((m for m in moedas if m["id"] == "bitcoin"), moedas[0])
    linha = {
        "buscado_em": buscado_em,
        "moedas_coletadas": len(moedas),
        "preco_bitcoin": bitcoin["preco"],
    }

    linhas_existentes = []
    if os.path.exists(caminho_csv):
        with open(caminho_csv, newline="", encoding="utf-8") as f:
            linhas_existentes = list(csv.DictReader(f))

    linhas_existentes.append(linha)
    # Mantém só as últimas HISTORICO_MAX_LINHAS — histórico real, mas
    # limitado (o repositório não deve crescer pra sempre).
    linhas_existentes = linhas_existentes[-HISTORICO_MAX_LINHAS:]

    with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["buscado_em", "moedas_coletadas", "preco_bitcoin"])
        writer.writeheader()
        writer.writerows(linhas_existentes)


def main():
    caminho_json, caminho_csv = caminhos()
    buscado_em = datetime.now(timezone.utc).isoformat(timespec="seconds")

    moedas_bruto = buscar_moedas()
    moedas = normalizar(moedas_bruto)

    salvar_snapshot(caminho_json, moedas, buscado_em)
    registrar_execucao(caminho_csv, buscado_em, moedas)

    print(f"Snapshot salvo com sucesso: {len(moedas)} moedas, em {buscado_em}")
    print(f"Salvo em: {caminho_json}")
    print(f"Histórico de execuções: {caminho_csv}")


if __name__ == "__main__":
    main()

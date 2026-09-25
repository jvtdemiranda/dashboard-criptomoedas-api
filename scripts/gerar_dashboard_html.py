"""
Gera o painel de criptomoedas em HTML (mobile-first) a partir de
data/atual.json (snapshot da API) e data/historico_execucoes.csv
(prova de que o pipeline roda periodicamente).

Segunda etapa do pipeline:
1. buscar_dados.py         -> gera data/atual.json e atualiza o histórico
2. gerar_dashboard_html.py -> monta public/index.html (este script)

dashboard_template.html é o esqueleto (HTML/CSS/JS); este script só
substitui o marcador /*__DATA__*/ pelo JSON combinado (snapshot atual +
histórico de execuções) e escreve o resultado em public/index.html —
pasta que o Vercel publica diretamente (Root Directory = public).
"""

import csv
import json
import os


def caminhos():
    pasta_raiz = os.path.join(os.path.dirname(__file__), "..")
    pasta_data = os.path.join(pasta_raiz, "data")
    template = os.path.join(os.path.dirname(__file__), "dashboard_template.html")
    pasta_public = os.path.join(pasta_raiz, "public")
    os.makedirs(pasta_public, exist_ok=True)
    return (
        os.path.join(pasta_data, "atual.json"),
        os.path.join(pasta_data, "historico_execucoes.csv"),
        template,
        os.path.join(pasta_public, "index.html"),
    )


def carregar_historico(caminho_csv: str) -> list[dict]:
    if not os.path.exists(caminho_csv):
        return []
    with open(caminho_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    caminho_snapshot, caminho_historico, template_path, html_saida = caminhos()

    with open(caminho_snapshot, encoding="utf-8") as f:
        snapshot = json.load(f)

    historico = carregar_historico(caminho_historico)

    dados_completos = {
        "buscado_em": snapshot["buscado_em"],
        "moeda_base": snapshot["moeda_base"],
        "moedas": snapshot["moedas"],
        "historico": historico,
    }
    dados_json = json.dumps(dados_completos, ensure_ascii=False, separators=(",", ":"))

    template = open(template_path, encoding="utf-8").read()
    html_final = template.replace("/*__DATA__*/", dados_json)

    with open(html_saida, "w", encoding="utf-8") as f:
        f.write(html_final)

    tamanho_kb = os.path.getsize(html_saida) / 1024
    print(f"Painel HTML gerado com sucesso: {html_saida}")
    print(f"Moedas: {len(snapshot['moedas'])} | Execuções no histórico: {len(historico)} | "
          f"Tamanho do arquivo: {tamanho_kb:.1f} KB")


if __name__ == "__main__":
    main()
